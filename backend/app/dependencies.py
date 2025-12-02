"""
Shared dependencies - Modern and optimized.
All reusable dependencies for FastAPI routes.
"""
from typing import Optional, Annotated
from fastapi import Depends, Header, Request
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
security = HTTPBearer(auto_error=False)

# Redis connection pool
_redis_client: Optional[Redis] = None


def get_redis() -> Redis:
    """
    Get Redis connection.
    Uses connection pooling for performance.
    """
    global _redis_client

    if _redis_client is None:
        _redis_client = Redis.from_url(
            settings.REDIS_URL,
            max_connections=settings.REDIS_MAX_CONNECTIONS,
            decode_responses=True,
            socket_timeout=5,
            socket_connect_timeout=5
        )
        logger.info("✅ Redis connection pool created")

    return _redis_client


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Raises:
        AuthenticationError: If no token provided
        InvalidTokenError: If token is invalid or expired
        UserNotFoundError: If user doesn't exist
    """
    if not credentials:
        raise AuthenticationError("Authentication required")

    token = credentials.credentials

    try:
        payload = decode_token(token)
        user_id: int = payload.get("sub")

        if user_id is None:
            raise InvalidTokenError()

    except (InvalidTokenError, Exception) as e:
        logger.warning(f"Invalid token attempt: {str(e)}")
        raise InvalidTokenError()

    # Get user from database
    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise UserNotFoundError()

    if not user.is_active:
        raise AuthenticationError("Account is disabled")

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current active user with additional checks.
    """
    if not current_user.is_active:
        raise AuthenticationError("Account is not active")
    return current_user


async def get_current_superuser(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Require superuser permissions.

    Raises:
        PermissionDeniedError: If user is not superuser
    """
    from app.core.exceptions import PermissionDeniedError

    if not current_user.is_superuser:
        logger.warning(f"Unauthorized admin access attempt by: {current_user.username}")
        raise PermissionDeniedError("Administrator access required")

    return current_user


async def get_optional_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, None otherwise.
    Useful for endpoints that work with or without auth.
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


async def check_rate_limit(
    request: Request,
    redis: Redis = Depends(get_redis)
):
    """
    Check rate limit for requests.
    Uses IP address or user_id as identifier.
    """
    if not settings.RATE_LIMIT_ENABLED:
        return

    # Get identifier (IP or user_id)
    identifier = request.client.host if request.client else "unknown"

    # Get user from request if authenticated
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            token = auth_header.replace("Bearer ", "")
            payload = decode_token(token)
            user_id = payload.get("sub")
            if user_id:
                identifier = f"user:{user_id}"
        except Exception:
            pass

    limiter = RateLimiter(redis)

    if not limiter.check_rate_limit(
        key=f"rate_limit:{identifier}",
        max_requests=settings.RATE_LIMIT_REQUESTS,
        window_seconds=settings.RATE_LIMIT_WINDOW
    ):
        remaining = limiter.get_remaining_requests(
            key=f"rate_limit:{identifier}",
            max_requests=settings.RATE_LIMIT_REQUESTS
        )

        logger.warning(f"⚠️ Rate limit exceeded for {identifier}")
        raise RateLimitError(retry_after=settings.RATE_LIMIT_WINDOW)


class Pagination:
    """Pagination helper with validation."""

    def __init__(
        self,
        skip: int = 0,
        limit: int = settings.DEFAULT_PAGE_SIZE
    ):
        # Validate and sanitize inputs
        self.skip = max(0, skip)
        self.limit = min(max(1, limit), settings.MAX_PAGE_SIZE)

    @property
    def page(self) -> int:
        """Calculate current page number (1-indexed)."""
        return (self.skip // self.limit) + 1

    @property
    def offset(self) -> int:
        """Get offset for database query."""
        return self.skip

    def __repr__(self) -> str:
        return f"Pagination(page={self.page}, skip={self.skip}, limit={self.limit})"


def get_pagination(
    skip: int = 0,
    limit: int = settings.DEFAULT_PAGE_SIZE
) -> Pagination:
    """
    Get pagination parameters with validation.

    Args:
        skip: Number of records to skip (default: 0)
        limit: Maximum records to return (default: from settings)

    Returns:
        Pagination object
    """
    return Pagination(skip=skip, limit=limit)


class CacheManager:
    """
    Redis cache manager with error handling.
    Gracefully handles cache failures.
    """

    def __init__(self, redis: Redis = Depends(get_redis)):
        self.redis = redis

    def get(self, key: str) -> Optional[str]:
        """
        Get value from cache.
        Returns None on error (fail-safe).
        """
        try:
            return self.redis.get(key)
        except Exception as e:
            logger.error(f"Cache get error for key '{key}': {e}")
            return None

    def set(self, key: str, value: str, ttl: int = 300) -> bool:
        """
        Set value in cache with TTL.
        Returns False on error (fail-safe).
        """
        try:
            self.redis.setex(key, ttl, value)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        """
        Delete key from cache.
        Returns False on error (fail-safe).
        """
        try:
            self.redis.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key '{key}': {e}")
            return False

    def clear_pattern(self, pattern: str) -> bool:
        """
        Delete all keys matching pattern.
        Returns False on error (fail-safe).
        """
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache clear pattern error for '{pattern}': {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        try:
            return bool(self.redis.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key '{key}': {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """
        Increment counter.
        Returns new value or None on error.
        """
        try:
            return self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key '{key}': {e}")
            return None

    def get_ttl(self, key: str) -> Optional[int]:
        """Get remaining TTL for key in seconds."""
        try:
            ttl = self.redis.ttl(key)
            return ttl if ttl > 0 else None
        except Exception as e:
            logger.error(f"Cache TTL error for key '{key}': {e}")
            return None


# Type annotations for cleaner code
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[Optional[User], Depends(get_optional_user)]
SuperUser = Annotated[User, Depends(get_current_superuser)]
DBSession = Annotated[Session, Depends(get_db)]
RedisClient = Annotated[Redis, Depends(get_redis)]
PaginationDep = Annotated[Pagination, Depends(get_pagination)]
CacheDep = Annotated[CacheManager, Depends(CacheManager)]