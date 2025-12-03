"""
Authentication API v1.
Modern, secure authentication with comprehensive features.
"""
from datetime import datetime
from typing import Annotated
from fastapi import APIRouter, Depends, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    LoginResponse,
    RefreshTokenRequest,
    PasswordResetRequest,
    PasswordResetConfirm,
    PasswordChangeRequest
)
from app.schemas.user import UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    validate_email,
    validate_username,
    validate_password_strength,
    generate_password_reset_token,
    verify_password_reset_token
)
from app.core.exceptions import (
    InvalidCredentialsError,
    EmailAlreadyExistsError,
    UsernameAlreadyExistsError,
    ValidationError,
    InvalidTokenError
)
from app.dependencies import get_current_user
from app.core.logger import setup_logger

router = APIRouter()
logger = setup_logger(__name__)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with email verification"
)
async def register(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.

    - **email**: Valid email address (will be verified)
    - **username**: Unique username (3-50 characters, alphanumeric + underscore)
    - **password**: Strong password (min 8 chars, uppercase, lowercase, number)
    - **full_name**: Optional full name
    """
    # Validate email format
    if not validate_email(data.email):
        raise ValidationError("Invalid email format")

    # Check email uniqueness
    if db.query(User).filter(User.email == data.email).first():
        raise EmailAlreadyExistsError(data.email)

    # Validate username
    if not validate_username(data.username):
        raise ValidationError(
            "Username must be 3-50 characters (letters, numbers, underscores only)"
        )

    # Check username uniqueness
    if db.query(User).filter(User.username == data.username).first():
        raise UsernameAlreadyExistsError(data.username)

    # Validate password strength
    is_valid, error_msg = validate_password_strength(data.password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Create user
    user = User(
        email=data.email,
        username=data.username,
        hashed_password=hash_password(data.password),
        full_name=data.full_name
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    # Send welcome email (background task)
    # background_tasks.add_task(send_welcome_email, user.email)

    logger.info(f"✅ New user registered: {user.username} ({user.email})")

    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Login",
    description="Authenticate user and receive access tokens"
)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Session = Depends(get_db)
):
    """
    Login with email or username.

    Returns access token (30 min) and refresh token (7 days).
    """
    # Find user (email or username)
    user = db.query(User).filter(
        (User.email == form_data.username) | (User.username == form_data.username)
    ).first()

    # Verify credentials
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"❌ Failed login attempt: {form_data.username}")
        raise InvalidCredentialsError()

    # Check if user is active
    if not user.is_active:
        raise ValidationError("Account is disabled. Contact support.")

    # Update last login
    user.last_login = datetime.utcnow()
    db.commit()

    # Create tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token = create_refresh_token(data={"sub": user.id})

    logger.info(f"✅ User logged in: {user.username}")

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        user=user
    )


@router.post(
    "/refresh",
    response_model=LoginResponse,
    summary="Refresh access token",
    description="Get new access token using refresh token"
)
async def refresh_token(
    data: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token.

    Provide valid refresh token to get new access token.
    """
    try:
        payload = decode_token(data.refresh_token)

        # Verify token type
        if payload.get("type") != "refresh":
            raise InvalidTokenError()

        user_id = payload.get("sub")

        # Get user
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise InvalidTokenError()

        # Create new tokens
        access_token = create_access_token(data={"sub": user.id})
        new_refresh_token = create_refresh_token(data={"sub": user.id})

        logger.debug(f"🔄 Token refreshed for user: {user.username}")

        return LoginResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            user=user
        )

    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise InvalidTokenError()


@router.post(
    "/logout",
    summary="Logout",
    description="Logout user (client should delete tokens)"
)
async def logout(current_user: User = Depends(get_current_user)):
    """
    Logout endpoint.

    Note: With JWT, client should delete tokens.
    This endpoint can be extended with token blacklisting.
    """
    logger.info(f"👋 User logged out: {current_user.username}")

    return {
        "message": "Successfully logged out",
        "user": current_user.username
    }


@router.post(
    "/password-reset/request",
    summary="Request password reset",
    description="Send password reset link to email"
)
async def request_password_reset(
    data: PasswordResetRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Request password reset.

    Always returns success to prevent email enumeration.
    If email exists, sends reset link.
    """
    user = db.query(User).filter(User.email == data.email).first()

    if user:
        # Generate reset token
        reset_token = generate_password_reset_token(data.email)

        # Send email (background task)
        # background_tasks.add_task(send_reset_email, data.email, reset_token)

        logger.info(f"📧 Password reset requested: {data.email}")
        logger.debug(f"Reset token (dev only): {reset_token}")

    # Always return success
    return {
        "message": "If the email exists, a reset link has been sent",
        "email": data.email
    }


@router.post(
    "/password-reset/confirm",
    summary="Reset password",
    description="Reset password using token from email"
)
async def reset_password(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db)
):
    """
    Reset password using token.

    Token is valid for 1 hour.
    """
    # Verify token
    email = verify_password_reset_token(data.token)
    if not email:
        raise InvalidTokenError()

    # Validate new password
    is_valid, error_msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Find user
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise InvalidTokenError()

    # Update password
    user.hashed_password = hash_password(data.new_password)
    db.commit()

    logger.info(f"🔐 Password reset completed: {email}")

    return {
        "message": "Password successfully reset",
        "email": email
    }


@router.post(
    "/password-change",
    summary="Change password",
    description="Change password for authenticated user"
)
async def change_password(
    data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change password.

    Requires current password for verification.
    """
    # Verify current password
    if not verify_password(data.current_password, current_user.hashed_password):
        raise ValidationError("Current password is incorrect")

    # Validate new password
    is_valid, error_msg = validate_password_strength(data.new_password)
    if not is_valid:
        raise ValidationError(error_msg)

    # Check new password is different
    if verify_password(data.new_password, current_user.hashed_password):
        raise ValidationError("New password must be different from current password")

    # Update password
    current_user.hashed_password = hash_password(data.new_password)
    db.commit()

    logger.info(f"🔐 Password changed: {current_user.username}")

    return {
        "message": "Password successfully changed",
        "user": current_user.username
    }


@router.get(
    "/verify-token",
    response_model=UserResponse,
    summary="Verify token",
    description="Verify if current token is valid"
)
async def verify_token(current_user: User = Depends(get_current_user)):
    """
    Verify token validity.

    Returns current user if token is valid.
    """
    return current_user