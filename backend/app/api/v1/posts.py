"""
Posts API v1.
Modern CRUD with search, filters, and caching.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, desc

from app.database import get_db
from app.dependencies import (
    get_current_user,
    get_optional_user,
    get_pagination,
    Pagination,
    CacheManager
)
from app.models.post import Post
from app.models.user import User
from app.schemas.post import (
    PostCreate,
    PostUpdate,
    PostResponse,
    PostListResponse,
    PostDetailResponse
)
from app.core.exceptions import PostNotFoundError, NotOwnerError, ValidationError
from app.core.security import sanitize_input
from app.config import settings
from app.core.logger import setup_logger
import json
import re

router = APIRouter()
logger = setup_logger(__name__)


def create_slug(title: str, db: Session) -> str:
    """
    Create unique URL-friendly slug.

    Args:
        title: Post title
        db: Database session

    Returns:
        Unique slug
    """
    # Create base slug
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)
    slug = re.sub(r'[\s_-]+', '-', slug)
    slug = slug.strip('-')[:200]  # Max 200 chars

    # Ensure uniqueness
    original_slug = slug
    counter = 1
    while db.query(Post).filter(Post.slug == slug).first():
        slug = f"{original_slug}-{counter}"
        counter += 1

    return slug


def generate_excerpt(content: str, max_length: int = 200) -> str:
    """
    Generate excerpt from content.

    Args:
        content: Full content
        max_length: Maximum excerpt length

    Returns:
        Excerpt string
    """
    if len(content) <= max_length:
        return content

    # Try to break at sentence
    excerpt = content[:max_length]
    last_period = excerpt.rfind('.')
    last_space = excerpt.rfind(' ')

    if last_period > max_length * 0.8:
        return excerpt[:last_period + 1]
    elif last_space > max_length * 0.8:
        return excerpt[:last_space] + "..."

    return excerpt + "..."


@router.get(
    "/",
    response_model=PostListResponse,
    summary="List posts",
    description="Get paginated list of posts with optional filters"
)
async def list_posts(
    pagination: Pagination = Depends(get_pagination),
    search: Optional[str] = Query(None, max_length=100, description="Search in title/content"),
    author_id: Optional[int] = Query(None, description="Filter by author ID"),
    author_username: Optional[str] = Query(None, description="Filter by author username"),
    published_only: bool = Query(True, description="Show only published posts"),
    sort_by: str = Query("created_at", description="Sort field (created_at, views, title)"),
    sort_order: str = Query("desc", description="Sort order (asc, desc)"),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    List posts with advanced filtering.

    - **search**: Search in title, content, excerpt
    - **author_id**: Filter by author ID
    - **author_username**: Filter by author username
    - **published_only**: Show only published (default: true)
    - **sort_by**: Sort field
    - **sort_order**: asc or desc
    """
    # Build cache key
    cache_key = f"posts:list:{pagination.skip}:{pagination.limit}:{search}:{author_id}:{author_username}:{published_only}:{sort_by}:{sort_order}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"💾 Cache hit: {cache_key}")
        return json.loads(cached)

    # Build query
    query = db.query(Post)

    # Filter published
    if published_only and not (current_user and current_user.is_superuser):
        query = query.filter(Post.published == True)

    # Filter by author ID
    if author_id:
        query = query.filter(Post.author_id == author_id)

    # Filter by author username
    if author_username:
        query = query.join(User).filter(User.username == author_username)

    # Search
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Post.title.ilike(search_pattern),
                Post.content.ilike(search_pattern),
                Post.excerpt.ilike(search_pattern)
            )
        )

    # Get total count
    total = query.count()

    # Sorting
    sort_field = getattr(Post, sort_by, Post.created_at)
    if sort_order.lower() == "desc":
        query = query.order_by(desc(sort_field))
    else:
        query = query.order_by(sort_field)

    # Paginate
    posts = query.offset(pagination.skip).limit(pagination.limit).all()

    # Build response
    response = PostListResponse(
        posts=[PostResponse.from_orm(p) for p in posts],
        total=total,
        page=pagination.page,
        page_size=pagination.limit,
        has_more=(pagination.skip + pagination.limit) < total
    )

    # Cache for 5 minutes
    cache.set(cache_key, response.model_dump_json(), ttl=settings.CACHE_TTL_POSTS)

    logger.debug(f"📄 Listed {len(posts)} posts (total: {total})")

    return response


@router.get(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="Get post by ID",
    description="Get single post with full details"
)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get post by ID and increment view count."""
    cache_key = f"post:id:{post_id}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        # Increment views in background
        db.query(Post).filter(Post.id == post_id).update(
            {Post.views: Post.views + 1},
            synchronize_session=False
        )
        db.commit()
        logger.debug(f"💾 Cache hit: post {post_id}")
        return json.loads(cached)

    # Query database
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions for unpublished
    if not post.published:
        if not current_user or (
            post.author_id != current_user.id and not current_user.is_superuser
        ):
            raise PostNotFoundError(post_id)

    # Increment views
    post.views += 1
    db.commit()
    db.refresh(post)

    # Cache for 10 minutes
    response = PostDetailResponse.from_orm(post)
    cache.set(cache_key, response.model_dump_json(), ttl=settings.CACHE_TTL_POST)

    logger.debug(f"👁️ Post viewed: {post.id} ({post.views} views)")

    return response


@router.get(
    "/slug/{slug}",
    response_model=PostDetailResponse,
    summary="Get post by slug",
    description="Get post by URL-friendly slug"
)
async def get_post_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get post by slug."""
    cache_key = f"post:slug:{slug}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        # Increment views
        post_data = json.loads(cached)
        db.query(Post).filter(Post.id == post_data["id"]).update(
            {Post.views: Post.views + 1},
            synchronize_session=False
        )
        db.commit()
        return json.loads(cached)

    # Query database
    post = db.query(Post).filter(Post.slug == slug).first()

    if not post:
        raise PostNotFoundError()

    # Check permissions
    if not post.published:
        if not current_user or (
            post.author_id != current_user.id and not current_user.is_superuser
        ):
            raise PostNotFoundError()

    # Increment views
    post.views += 1
    db.commit()
    db.refresh(post)

    # Cache
    response = PostDetailResponse.from_orm(post)
    cache.set(cache_key, response.model_dump_json(), ttl=settings.CACHE_TTL_POST)

    return response


@router.post(
    "/",
    response_model=PostDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create post",
    description="Create new blog post"
)
async def create_post(
    data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Create new post."""
    # Sanitize inputs
    title = sanitize_input(data.title, max_length=200)
    content = sanitize_input(data.content, max_length=50000)

    # Validate lengths
    if len(title) < 3:
        raise ValidationError("Title must be at least 3 characters")
    if len(content) < 10:
        raise ValidationError("Content must be at least 10 characters")

    # Create slug
    slug = create_slug(title, db)

    # Generate excerpt
    excerpt = data.excerpt
    if not excerpt:
        excerpt = generate_excerpt(content)
    else:
        excerpt = sanitize_input(excerpt, max_length=500)

    # Create post
    post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt,
        published=data.published,
        author_id=current_user.id
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    # Invalidate cache
    cache.clear_pattern("posts:list:*")

    logger.info(f"✅ Post created: '{post.title}' by {current_user.username} (ID: {post.id})")

    return post


@router.put(
    "/{post_id}",
    response_model=PostDetailResponse,
    summary="Update post",
    description="Update existing post"
)
async def update_post(
    post_id: int,
    data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Update post."""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions
    if post.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("post")

    # Update fields
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        if value is not None:
            if field == "title":
                value = sanitize_input(value, max_length=200)
                # Update slug if title changed
                if value != post.title:
                    setattr(post, "slug", create_slug(value, db))
            elif field == "content":
                value = sanitize_input(value, max_length=50000)
            elif field == "excerpt":
                value = sanitize_input(value, max_length=500)

            setattr(post, field, value)

    db.commit()
    db.refresh(post)

    # Invalidate cache
    cache.delete(f"post:id:{post_id}")
    cache.delete(f"post:slug:{post.slug}")
    cache.clear_pattern("posts:list:*")

    logger.info(f"✏️ Post updated: '{post.title}' (ID: {post.id})")

    return post


@router.delete(
    "/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete post",
    description="Delete post permanently"
)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Delete post."""
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions
    if post.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("post")

    title = post.title
    slug = post.slug

    db.delete(post)
    db.commit()

    # Invalidate cache
    cache.delete(f"post:id:{post_id}")
    cache.delete(f"post:slug:{slug}")
    cache.clear_pattern("posts:list:*")

    logger.info(f"🗑️ Post deleted: '{title}' (ID: {post_id})")


@router.get(
    "/popular/top",
    response_model=List[PostResponse],
    summary="Popular posts",
    description="Get most popular posts by views"
)
async def get_popular_posts(
    limit: int = Query(10, ge=1, le=50, description="Number of posts"),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Get most popular posts."""
    cache_key = f"posts:popular:{limit}"

    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    posts = db.query(Post).filter(
        Post.published == True
    ).order_by(
        desc(Post.views)
    ).limit(limit).all()

    result = [PostResponse.from_orm(p) for p in posts]

    # Cache for 10 minutes
    cache.set(
        cache_key,
        json.dumps([p.model_dump() for p in result]),
        ttl=600
    )

    logger.debug(f"📊 Popular posts retrieved: {len(posts)}")

    return result


@router.get(
    "/recent/latest",
    response_model=List[PostResponse],
    summary="Recent posts",
    description="Get most recent posts"
)
async def get_recent_posts(
    limit: int = Query(10, ge=1, le=50, description="Number of posts"),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Get most recent posts."""
    cache_key = f"posts:recent:{limit}"

    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    posts = db.query(Post).filter(
        Post.published == True
    ).order_by(
        desc(Post.created_at)
    ).limit(limit).all()

    result = [PostResponse.from_orm(p) for p in posts]

    # Cache for 5 minutes
    cache.set(
        cache_key,
        json.dumps([p.model_dump() for p in result]),
        ttl=300
    )

    return result