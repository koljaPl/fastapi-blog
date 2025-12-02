"""
Posts API endpoints - improved version.
Complete CRUD with caching, pagination, and search.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

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
from app.schemas.post import PostCreate, PostUpdate, PostResponse, PostListResponse
from app.core.exceptions import (
    PostNotFoundError,
    NotOwnerError,
    ValidationError,
    ContentTooLongError
)
from app.core.security import sanitize_input
from app.config import settings
from app.core.logger import setup_logger
import json

router = APIRouter()
logger = setup_logger(__name__)


def create_slug(title: str) -> str:
    """Create URL-friendly slug from title."""
    import re
    slug = title.lower()
    slug = re.sub(r'[^\w\s-]', '', slug)  # Remove special chars
    slug = re.sub(r'[\s_-]+', '-', slug)  # Replace spaces with hyphens
    slug = slug.strip('-')
    return slug


@router.get("/", response_model=PostListResponse)
async def get_posts(
    pagination: Pagination = Depends(get_pagination),
    search: Optional[str] = Query(None, max_length=100),
    author_id: Optional[int] = None,
    published_only: bool = True,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """
    Get all posts with pagination and optional search.

    Args:
        pagination: Pagination parameters
        search: Search query for title/content
        author_id: Filter by author
        published_only: Show only published posts

    Returns:
        List of posts with pagination info
    """
    # Build cache key
    cache_key = f"posts:{pagination.skip}:{pagination.limit}:{search}:{author_id}:{published_only}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f"Cache hit: {cache_key}")
        return json.loads(cached)

    # Build query
    query = db.query(Post)

    if published_only:
        query = query.filter(Post.published == True)

    if author_id:
        query = query.filter(Post.author_id == author_id)

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

    # Get posts
    posts = query.order_by(
        Post.created_at.desc()
    ).offset(pagination.skip).limit(pagination.limit).all()

    # Build response
    response = {
        "posts": [PostResponse.from_orm(p).dict() for p in posts],
        "total": total,
        "page": pagination.page,
        "page_size": pagination.limit,
        "has_more": (pagination.skip + pagination.limit) < total
    }

    # Cache for 5 minutes
    cache.set(cache_key, json.dumps(response), ttl=settings.CACHE_TTL_POSTS)

    return response


@router.get("/{post_id}", response_model=PostResponse)
async def get_post(
    post_id: int,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Get single post by ID.
    Increments view count.
    """
    cache_key = f"post:{post_id}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        # Increment views in background
        db.query(Post).filter(Post.id == post_id).update(
            {Post.views: Post.views + 1},
            synchronize_session=False
        )
        db.commit()

        return json.loads(cached)

    # Query database
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions for unpublished posts
    if not post.published:
        if not current_user or (post.author_id != current_user.id and not current_user.is_superuser):
            raise PostNotFoundError(post_id)

    # Increment views
    post.views += 1
    db.commit()
    db.refresh(post)

    # Cache for 10 minutes
    post_data = PostResponse.from_orm(post).dict()
    cache.set(cache_key, json.dumps(post_data), ttl=settings.CACHE_TTL_POST)

    return post


@router.get("/slug/{slug}", response_model=PostResponse)
async def get_post_by_slug(
    slug: str,
    db: Session = Depends(get_db),
    cache: CacheManager = Depends(),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """Get post by slug (URL-friendly identifier)."""
    cache_key = f"post:slug:{slug}"

    # Try cache
    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    post = db.query(Post).filter(Post.slug == slug).first()

    if not post:
        raise PostNotFoundError()

    # Check permissions
    if not post.published:
        if not current_user or (post.author_id != current_user.id and not current_user.is_superuser):
            raise PostNotFoundError()

    # Increment views
    post.views += 1
    db.commit()
    db.refresh(post)

    # Cache
    post_data = PostResponse.from_orm(post).dict()
    cache.set(cache_key, json.dumps(post_data), ttl=settings.CACHE_TTL_POST)

    return post


@router.post("/", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_data: PostCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """
    Create new post.
    Requires authentication.
    """
    # Sanitize inputs
    title = sanitize_input(post_data.title, max_length=200)
    content = sanitize_input(post_data.content, max_length=50000)

    if len(title) < 3:
        raise ValidationError("Title must be at least 3 characters")

    if len(content) < 10:
        raise ValidationError("Content must be at least 10 characters")

    # Create slug
    slug = create_slug(title)

    # Ensure unique slug
    existing = db.query(Post).filter(Post.slug == slug).first()
    if existing:
        # Add number suffix
        count = db.query(Post).filter(Post.slug.like(f"{slug}%")).count()
        slug = f"{slug}-{count + 1}"

    # Create excerpt if not provided
    excerpt = post_data.excerpt
    if not excerpt:
        excerpt = content[:200] + "..." if len(content) > 200 else content
    else:
        excerpt = sanitize_input(excerpt, max_length=500)

    # Create post
    post = Post(
        title=title,
        slug=slug,
        content=content,
        excerpt=excerpt,
        published=post_data.published,
        author_id=current_user.id
    )

    db.add(post)
    db.commit()
    db.refresh(post)

    # Invalidate cache
    cache.clear_pattern("posts:*")

    logger.info(f"Post created: '{post.title}' by {current_user.username} (ID: {post.id})")

    return post


@router.put("/{post_id}", response_model=PostResponse)
async def update_post(
    post_id: int,
    post_data: PostUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """
    Update post.
    Only author or admin can update.
    """
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions
    if post.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("post")

    # Update fields
    update_data = post_data.dict(exclude_unset=True)

    for field, value in update_data.items():
        if field == "title" and value:
            value = sanitize_input(value, max_length=200)
            # Update slug if title changed
            if value != post.title:
                setattr(post, "slug", create_slug(value))
        elif field == "content" and value:
            value = sanitize_input(value, max_length=50000)
        elif field == "excerpt" and value:
            value = sanitize_input(value, max_length=500)

        setattr(post, field, value)

    db.commit()
    db.refresh(post)

    # Invalidate cache
    cache.delete(f"post:{post_id}")
    cache.delete(f"post:slug:{post.slug}")
    cache.clear_pattern("posts:*")

    logger.info(f"Post updated: '{post.title}' (ID: {post.id})")

    return post


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
    post_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """
    Delete post.
    Only author or admin can delete.
    """
    post = db.query(Post).filter(Post.id == post_id).first()

    if not post:
        raise PostNotFoundError(post_id)

    # Check permissions
    if post.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("post")

    slug = post.slug
    title = post.title

    db.delete(post)
    db.commit()

    # Invalidate cache
    cache.delete(f"post:{post_id}")
    cache.delete(f"post:slug:{slug}")
    cache.clear_pattern("posts:*")

    logger.info(f"Post deleted: '{title}' (ID: {post_id})")

    return None


@router.get("/stats/popular", response_model=List[PostResponse])
async def get_popular_posts(
    limit: int = Query(5, ge=1, le=20),
    db: Session = Depends(get_db),
    cache: CacheManager = Depends()
):
    """Get most popular posts by view count."""
    cache_key = f"posts:popular:{limit}"

    cached = cache.get(cache_key)
    if cached:
        return json.loads(cached)

    posts = db.query(Post).filter(
        Post.published == True
    ).order_by(
        Post.views.desc()
    ).limit(limit).all()

    result = [PostResponse.from_orm(p).dict() for p in posts]

    # Cache for 10 minutes
    cache.set(cache_key, json.dumps(result), ttl=600)

    return result