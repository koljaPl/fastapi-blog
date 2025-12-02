"""
Authentication API endpoints.
Secure user registration, login, and token management.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, TokenResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    validate_email,
    validate_username,
    validate_password_strength
)
from app.core.exceptions import (
    InvalidCredentialsError,
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    ValidationError
)
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
        user_data: UserCreate,
        db: Session = Depends(get_db)
):
    """
    Register new user account.

    Validates:
    - Email format and uniqueness
    - Username format and uniqueness
    - Password strength

    Returns:
        Created user object
    """
    # Validate email
    if not validate_email(user_data.email):
        raise ValidationError("Invalid email format")

    # Check if email exists
    if db.query(User).filter(User.email == user_data.email).first():
        raise EmailAlreadyExistsError(user_data.email)

    # Validate username
    if not validate_username(user_data.username):
        raise ValidationError(
            "Username must be 3-50 characters and contain only letters, numbers, and underscores"
        )

    # Check if username exists
    if db.query(User).filter(User.username == user_data.username).first():
        raise UsernameAlreadyExistsError(user_data.username)

    # Validate password strength
    is_valid, error_msg = validate_password_strength(user_data.password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Create user
    hashed_password = hash_password(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    logger.info(f"New user registered: {user.username} ({user.email})")

    return user


@router.post("/login", response_model=TokenResponse)
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: Session = Depends(get_db)
):
    """
    Login with email/username and password.

    Args:
        form_data: OAuth2 form with username (email) and password

    Returns:
        Access token and refresh token
    """
    # Find user by email or username
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()

    # Verify user exists and password is correct
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Failed login attempt for: {form_data.username}")
        raise InvalidCredentialsError()

    # Check if user is active
    if not user.is_active:
        raise ValidationError("Account is disabled")

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    logger.info(f"User logged in: {user.username}")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
        refresh_token: str,
        db: Session = Depends(get_db)
):
    """
    Get new access token using refresh token.

    Args:
        refresh_token: Valid refresh token

    Returns:
        New access token and refresh token
    """
    from app.core.security import decode_token
    from app.core.exceptions import InvalidTokenError

    try:
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise InvalidTokenError()

        user_id = payload.get("sub")

        # Verify user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise InvalidTokenError()

        # Create new tokens
        new_access_token = create_access_token(data={"sub": user.id})
        new_refresh_token = create_refresh_token(data={"sub": user.id})

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }

    except Exception:
        raise InvalidTokenError()


@router.post("/logout")
async def logout():
    """
    Logout endpoint.

    Note: With JWT, logout is handled client-side by removing the token.
    This endpoint is for consistency and can be extended with token blacklisting.
    """
    # In production, you might want to:
    # 1. Blacklist the token in Redis
    # 2. Track logout events
    # 3. Revoke refresh tokens

    return {"message": "Successfully logged out"}


@router.post("/password-reset-request")
async def request_password_reset(
        email: str,
        db: Session = Depends(get_db)
):
    """
    Request password reset email.

    Note: Always returns success to prevent email enumeration.
    """
    user = db.query(User).filter(User.email == email).first()

    if user:
        # In production: send email with reset token
        from app.core.security import generate_password_reset_token
        reset_token = generate_password_reset_token(email)

        # TODO: Send email with reset link
        logger.info(f"Password reset requested for: {email}")
        # For now, just log the token (in production, send via email)
        logger.debug(f"Reset token: {reset_token}")

    # Always return success to prevent email enumeration
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/password-reset")
async def reset_password(
        token: str,
        new_password: str,
        db: Session = Depends(get_db)
):
    """
    Reset password using token from email.

    Args:
        token: Password reset token
        new_password: New password

    Returns:
        Success message
    """
    from app.core.security import verify_password_reset_token
    from app.core.exceptions import InvalidTokenError

    email = verify_password_reset_token(token)

    if not email:
        raise InvalidTokenError()

    # Validate new password
    is_valid, error_msg = validate_password_strength(new_password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Update password
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise InvalidTokenError()

    user.hashed_password = hash_password(new_password)
    db.commit()

    logger.info(f"Password reset completed for: {email}")

    return {"message": "Password successfully reset"}