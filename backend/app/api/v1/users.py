"""
Users API endpoints.
Profile management and user operations.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, PasswordChange
from app.core.security import hash_password, verify_password
from app.core.exceptions import UserNotFoundError, ValidationError
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.get("/me", response_model=UserResponse)
async def get_current_user_profile(
        current_user: User = Depends(get_current_user)
):
    """Get current user's profile."""
    return current_user


@router.put("/me", response_model=UserResponse)
async def update_current_user(
        user_data: UserUpdate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Update current user's profile."""
    update_data = user_data.dict(exclude_unset=True)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    db.commit()
    db.refresh(current_user)

    logger.info(f"User profile updated: {current_user.username}")

    return current_user


@router.post("/me/change-password")
async def change_password(
        password_data: PasswordChange,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    """Change current user's password."""
    # Verify old password
    if not verify_password(password_data.old_password, current_user.hashed_password):
        raise ValidationError("Current password is incorrect")

    # Validate new password
    from app.core.security import validate_password_strength
    is_valid, error_msg = validate_password_strength(password_data.new_password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Update password
    current_user.hashed_password = hash_password(password_data.new_password)
    db.commit()

    logger.info(f"Password changed for user: {current_user.username}")

    return {"message": "Password successfully changed"}


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
        user_id: int,
        db: Session = Depends(get_db)
):
    """Get user by ID."""
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise UserNotFoundError(str(user_id))

    return user


@router.get("/username/{username}", response_model=UserResponse)
async def get_user_by_username(
        username: str,
        db: Session = Depends(get_db)
):
    """Get user by username."""
    user = db.query(User).filter(User.username == username).first()

    if not user:
        raise UserNotFoundError(username)

    return user