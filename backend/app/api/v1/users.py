"""
Users API v1.
User profile management and operations.
"""
from typing import List
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_current_superuser, get_pagination, Pagination
from app.models.user import User
from app.models.post import Post
from app.schemas.user import UserResponse, UserUpdate, UserDetailResponse, UserListResponse
from app.schemas.post import PostResponse
from app.core.exceptions import UserNotFoundError, ValidationError
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.get(
    "/me",
    response_model=UserDetailResponse,
    summary="Get current user",
    description="Get authenticated user's profile"
)
async def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's full profile."""
    return current_user


@router.put(
    "/me",
    response_model=UserDetailResponse,
    summary="Update profile",
    description="Update current user's profile"
)
async def update_current_user_profile(
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile."""
    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    logger.info(f"✏️ Profile updated: {current_user.username}")

    return current_user


@router.delete(
    "/me",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete account",
    description="Delete current user's account (soft delete)"
)
async def delete_current_user_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete current user's account."""
    current_user.is_active = False
    db.commit()

    logger.info(f"🗑️ Account deactivated: {current_user.username}")


@router.get(
    "/me/posts",
    response_model=List[PostResponse],
    summary="Get my posts",
    description="Get all posts by current user"
)
async def get_my_posts(
    current_user: User = Depends(get_current_user),
    pagination: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db)
):
    """Get all posts by current user."""
    posts = db.query(Post).filter(
        Post.author_id == current_user.id
    ).order_by(
        Post.created_at.desc()
    ).offset(pagination.skip).limit(pagination.limit).all()

    return posts


@router.get(
    "/",
    response_model=UserListResponse,
    summary="List users",
    description="Get list of users (admin only)"
)
async def list_users(
    pagination: Pagination = Depends(get_pagination),
    search: str = Query(None, max_length=100, description="Search by username or email"),
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """List all users (admin only)."""
    query = db.query(User)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.username.ilike(search_pattern)) |
            (User.email.ilike(search_pattern))
        )

    total = query.count()
    users = query.offset(pagination.skip).limit(pagination.limit).all()

    return UserListResponse(
        users=[UserResponse.from_orm(u) for u in users],
        total=total,
        page=pagination.page,
        page_size=pagination.limit,
        has_more=(pagination.skip + pagination.limit) < total
    )


@router.get(
    "/{user_id}",
    response_model=UserDetailResponse,
    summary="Get user by ID",
    description="Get user profile by ID"
)
async def get_user_by_id(user_id: int, db: Session = Depends(get_db)):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(str(user_id))

    return user


@router.get(
    "/username/{username}",
    response_model=UserDetailResponse,
    summary="Get user by username",
    description="Get user profile by username"
)
async def get_user_by_username(username: str, db: Session = Depends(get_db)):
    """Get user by username."""
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise UserNotFoundError(username)

    return user


@router.get(
    "/{user_id}/posts",
    response_model=List[PostResponse],
    summary="Get user's posts",
    description="Get all published posts by user"
)
async def get_user_posts(
    user_id: int,
    pagination: Pagination = Depends(get_pagination),
    db: Session = Depends(get_db)
):
    """Get all published posts by user."""
    # Check if user exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise UserNotFoundError(str(user_id))

    posts = db.query(Post).filter(
        Post.author_id == user_id,
        Post.published == True
    ).order_by(
        Post.created_at.desc()
    ).offset(pagination.skip).limit(pagination.limit).all()

    return posts


@router.patch(
    "/{user_id}/activate",
    response_model=UserResponse,
    summary="Activate user",
    description="Activate user account (admin only)"
)
async def activate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Activate user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(str(user_id))

    user.is_active = True
    db.commit()
    db.refresh(user)

    logger.info(f"✅ User activated: {user.username} by {current_user.username}")

    return user


@router.patch(
    "/{user_id}/deactivate",
    response_model=UserResponse,
    summary="Deactivate user",
    description="Deactivate user account (admin only)"
)
async def deactivate_user(
    user_id: int,
    current_user: User = Depends(get_current_superuser),
    db: Session = Depends(get_db)
):
    """Deactivate user account (admin only)."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(str(user_id))

    if user.is_superuser:
        raise ValidationError("Cannot deactivate superuser")

    user.is_active = False
    db.commit()
    db.refresh(user)

    logger.info(f"🚫 User deactivated: {user.username} by {current_user.username}")

    return user