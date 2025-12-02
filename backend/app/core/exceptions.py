"""
Custom exceptions for better error handling.
Clear, specific, and user-friendly errors.
"""
from fastapi import HTTPException, status


class BlogException(HTTPException):
    """Base exception for all blog errors."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        super().__init__(status_code=status_code, detail=detail)


# Authentication Exceptions
class AuthenticationError(BlogException):
    """Base auth error."""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)


class InvalidCredentialsError(AuthenticationError):
    """Wrong email or password."""

    def __init__(self):
        super().__init__("Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """JWT token expired."""

    def __init__(self):
        super().__init__("Token has expired, please login again")


class InvalidTokenError(AuthenticationError):
    """Invalid JWT token."""

    def __init__(self):
        super().__init__("Invalid authentication token")


# Authorization Exceptions
class PermissionDeniedError(BlogException):
    """User doesn't have permission."""

    def __init__(self, detail: str = "You don't have permission to perform this action"):
        super().__init__(detail, status.HTTP_403_FORBIDDEN)


class NotOwnerError(PermissionDeniedError):
    """User is not the owner of resource."""

    def __init__(self, resource: str = "resource"):
        super().__init__(f"You are not the owner of this {resource}")


# Resource Exceptions
class NotFoundError(BlogException):
    """Resource not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found", status.HTTP_404_NOT_FOUND)


class PostNotFoundError(NotFoundError):
    """Post doesn't exist."""

    def __init__(self, post_id: int = None):
        detail = f"Post with id {post_id} not found" if post_id else "Post not found"
        super().__init__(detail)


class UserNotFoundError(NotFoundError):
    """User doesn't exist."""

    def __init__(self, identifier: str = None):
        detail = f"User {identifier} not found" if identifier else "User not found"
        super().__init__(detail)


# Validation Exceptions
class ValidationError(BlogException):
    """Data validation error."""

    def __init__(self, detail: str):
        super().__init__(detail, status.HTTP_422_UNPROCESSABLE_ENTITY)


class AlreadyExistsError(ValidationError):
    """Resource already exists."""

    def __init__(self, resource: str, field: str, value: str):
        super().__init__(f"{resource} with {field} '{value}' already exists")


class EmailAlreadyExistsError(AlreadyExistsError):
    """Email is taken."""

    def __init__(self, email: str):
        super().__init__("User", "email", email)


class UsernameAlreadyExistsError(AlreadyExistsError):
    """Username is taken."""

    def __init__(self, username: str):
        super().__init__("User", "username", username)


class SlugAlreadyExistsError(AlreadyExistsError):
    """Post slug is taken."""

    def __init__(self, slug: str):
        super().__init__("Post", "slug", slug)


# Rate Limiting
class RateLimitError(BlogException):
    """Too many requests."""

    def __init__(self, retry_after: int = 60):
        super().__init__(
            f"Too many requests. Please try again in {retry_after} seconds",
            status.HTTP_429_TOO_MANY_REQUESTS
        )


# Database Exceptions
class DatabaseError(BlogException):
    """Database operation failed."""

    def __init__(self, detail: str = "Database operation failed"):
        super().__init__(detail, status.HTTP_500_INTERNAL_SERVER_ERROR)


class CacheError(BlogException):
    """Redis cache error."""

    def __init__(self, detail: str = "Cache operation failed"):
        super().__init__(detail, status.HTTP_500_INTERNAL_SERVER_ERROR)


# Content Exceptions
class ContentTooLongError(ValidationError):
    """Content exceeds max length."""

    def __init__(self, field: str, max_length: int):
        super().__init__(f"{field} must not exceed {max_length} characters")


class InvalidContentError(ValidationError):
    """Content contains invalid data."""

    def __init__(self, reason: str):
        super().__init__(f"Invalid content: {reason}")


# Helper function for consistent error responses
def error_response(error: Exception) -> dict:
    """Convert exception to JSON response."""
    if isinstance(error, BlogException):
        return {
            "error": error.__class__.__name__,
            "detail": error.detail,
            "status_code": error.status_code
        }

    return {
        "error": "InternalServerError",
        "detail": "An unexpected error occurred",
        "status_code": 500
    }