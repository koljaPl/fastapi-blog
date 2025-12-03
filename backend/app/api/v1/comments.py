"""
Comments API v1.
Commenting system for blog posts.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_optional_user, get_pagination, Pagination
from app.models.post import Post, Comment
from app.models.user import User
from app.schemas.comment import (
    CommentCreate,
    CommentUpdate,
    CommentResponse,
    CommentListResponse
)
from app.core.exceptions import (
    PostNotFoundError,
    NotFoundError,
    NotOwnerError,
    ValidationError
)
from app.core.security import sanitize_input
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.get(
    "/post/{post_id}",
    response_model=CommentListResponse,
    summary="Get post comments",
    description="Get all comments for a post"
)
async def get_post_comments(
        post_id: int,
        pagination: Pagination = Depends(get_pagination),
        sort_order: str = Query("desc", description="Sort order (asc, desc)"),
        db: Session = Depends(get_db)
):
    """Get all comments for a post."""
    # Check if post exists
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)

    # Build query
    query = db.query(Comment).filter(Comment.post_id == post_id)

    # Sort
    if sort_order.lower() == "asc":
        query = query.order_by(Comment.created_at.asc())
    else:
        query = query.order_by(Comment.created_at.desc())

    # Get total
    total = query.count()

    # Paginate
    comments = query.offset(pagination.skip).limit(pagination.limit).all()

    logger.debug(f"📝 Retrieved {len(comments)} comments for post {post_id}")

    return CommentListResponse(
        comments=[CommentResponse.from_orm(c) for c in comments],
        total=total,
        page=pagination.page,
        page_size=pagination.limit,
        has_more=(pagination.skip + pagination.limit) < total
    )


@router.get(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Get comment",
    description="Get single comment by ID"
)
async def get_comment(comment_id: int, db: Session = Depends(get_db)):
    """Get comment by ID."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()

    if not comment:
        raise NotFoundError("Comment")

    return comment


@router.post(
    "/post/{post_id}",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create comment",
    description="Add comment to a post"
)
async def create_comment(
        post_id: int,
        data: CommentCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Create a new comment on a post."""
    # Check if post exists and is published
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise PostNotFoundError(post_id)

    if not post.published:
        raise ValidationError("Cannot comment on unpublished post")

    # Sanitize content
    content = sanitize_input(data.content, max_length=2000)

    if len(content) < 1:
        raise ValidationError("Comment cannot be empty")

    # Create comment
    comment = Comment(
        content=content,
        post_id=post_id,
        author_id=current_user.id
    )

    db.add(comment)
    db.commit()
    db.refresh(comment)

    logger.info(
        f"💬 Comment created on post {post_id} by {current_user.username} (ID: {comment.id})"
    )

    return comment


@router.put(
    "/{comment_id}",
    response_model=CommentResponse,
    summary="Update comment",
    description="Update own comment"
)
async def update_comment(
        comment_id: int,
        data: CommentUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update a comment."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()

    if not comment:
        raise NotFoundError("Comment")

    # Check permissions
    if comment.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("comment")

    # Update content
    if data.content:
        content = sanitize_input(data.content, max_length=2000)
        if len(content) < 1:
            raise ValidationError("Comment cannot be empty")
        comment.content = content

    db.commit()
    db.refresh(comment)

    logger.info(f"✏️ Comment updated: {comment_id}")

    return comment


@router.delete(
    "/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete comment",
    description="Delete own comment or any comment (admin)"
)
async def delete_comment(
        comment_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Delete a comment."""
    comment = db.query(Comment).filter(Comment.id == comment_id).first()

    if not comment:
        raise NotFoundError("Comment")

    # Check permissions
    if comment.author_id != current_user.id and not current_user.is_superuser:
        raise NotOwnerError("comment")

    db.delete(comment)
    db.commit()

    logger.info(f"🗑️ Comment deleted: {comment_id}")


@router.get(
    "/user/{user_id}",
    response_model=List[CommentResponse],
    summary="Get user comments",
    description="Get all comments by a user"
)
async def get_user_comments(
        user_id: int,
        pagination: Pagination = Depends(get_pagination),
        db: Session = Depends(get_db)
):
    """Get all comments by a user."""
    comments = db.query(Comment).filter(
        Comment.author_id == user_id
    ).order_by(
        Comment.created_at.desc()
    ).offset(pagination.skip).limit(pagination.limit).all()

    return comments


@router.get(
    "/me/my-comments",
    response_model=List[CommentResponse],
    summary="Get my comments",
    description="Get all comments by current user"
)
async def get_my_comments(
        pagination: Pagination = Depends(get_pagination),
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Get all comments by current user."""
    comments = db.query(Comment).filter(
        Comment.author_id == current_user.id
    ).order_by(
        Comment.created_at.desc()
    ).offset(pagination.skip).limit(pagination.limit).all()

    return comments