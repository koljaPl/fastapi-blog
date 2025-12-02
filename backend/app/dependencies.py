"""
Shared dependencies for FastAPI routes.
Authentication, Redis, rate limiting, etc.
"""
from typing import Optional
from fastapi import Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from redis import Redis

from app.database import get_db
from app.models.user import User
from app.core.security import decode_token, RateLimiter
from app.core.exceptions import (
    AuthenticationError,
    InvalidTokenError,
    UserNotFoundError,
    RateLimitError
)
from app.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Security scheme
security = HTTPBearer()

# Redis connection
_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """
    Get Redis connection.
    Creates connection on first use.
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True
        )
        logger.info("✅ Redis connection established")

    return _redis_client


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        credentials: Bearer token from Authorization header
        db: Database session

    Returns:
        Current user object

    Raises:
        InvalidTokenError: If token is invalid
        UserNotFoundError: If user doesn't exist
    """
    token = credentials.credentials

    try:
        payload = decode_token(token)
        user_id: int = payload.get("sub")

        if user_id is None:
            raise InvalidTokenError()

    except InvalidTokenError:
        raise

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise UserNotFoundError()

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    return user


async def get_current_active_user(
        current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.
    Additional check for active status.
    """
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")
    return current_user


async def get_current_superuser(
        current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current user and verify they are a superuser.

    Args:
        current_user: Current authenticated user

    Returns:
        User if they are superuser

    Raises:
        PermissionDeniedError: If user is not superuser
    """
    from app.core.exceptions import PermissionDeniedError

    if not current_user.is_superuser:
        raise PermissionDeniedError("Superuser access required")

    return current_user


async def get_optional_user(
        authorization: Optional[str] = Header(None),
        db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work with or without auth.

    Args:
        authorization: Optional Authorization header
        db: Database session

    Returns:
        User object or None
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    try:
        token = authorization.replace("Bearer ", "")
        payload = decode_token(token)
        user_id: int = payload.get("sub")

        if user_id is None:
            return None

        user = db.query(User).filter(User.id == user_id).first()
        return user if user and user.is_active else None

    except Exception:
        return None


async def rate_limit_check(
        request_id: str,
        redis: Redis = Depends(get_redis)
):
    """
    Check rate limit for requests.

    Args:
        request_id: Unique identifier (IP, user_id, etc.)
        redis: Redis connection

    Raises:
        RateLimitError: If rate limit exceeded
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    limiter = RateLimiter(redis)

    if not limiter.check_rate_limit(
            key=f"rate_limit:{request_id}",
            max_requests=settings.RATE_LIMIT_REQUESTS,
            window_seconds=settings.RATE_LIMIT_WINDOW
    ):
        remaining = limiter.get_remaining_requests(
            key=f"rate_limit:{request_id}",
            max_requests=settings.RATE_LIMIT_REQUESTS
        )

        logger.warning(f"Rate limit exceeded for {request_id}")
        raise RateLimitError(retry_after=settings.RATE_LIMIT_WINDOW)


class Pagination:
    """Pagination helper."""

    def __init__(
            self,
            skip: int = 0,
            limit: int = settings.DEFAULT_PAGE_SIZE
    ):
        self.skip = max(0, skip)
        self.limit = min(limit, settings.MAX_PAGE_SIZE)

        if self.limit <= 0:
            self.limit = settings.DEFAULT_PAGE_SIZE

    @property
    def page(self) -> int:
        """Calculate current page number."""
        return (self.skip // self.limit) + 1


def get_pagination(
        skip: int = 0,
        limit: int = settings.DEFAULT_PAGE_SIZE
) -> Pagination:
    """
    Get pagination parameters.

    Args:
        skip: Number of records to skip
        limit: Maximum records to return

    Returns:
        Pagination object
    """
    return Pagination(skip=skip, limit=limit)


# Cache dependency
class CacheManager:
    """Helper for cache operations."""

    def __init__(self, redis: Redis = Depends(get_redis)):
        self.redis = redis

    def get(self, key: str) -> Optional[str]:
        """Get value from cache."""
        try:
            return self.redis.get(key)
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 300):
        """Set value in cache with TTL."""
        try:
            self.redis.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Cache set error: {e}")

    def delete(self, key: str):
        """Delete key from cache."""
        try:
            self.redis.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error: {e}")

    def clear_pattern(self, pattern: str):
        """Delete all keys matching pattern."""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache clear pattern error: {e}")