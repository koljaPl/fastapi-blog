"""
Global error handler for consistent error responses.
Catches all exceptions and formats them properly.
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError

from app.core.exceptions import BlogException, DatabaseError, CacheError
from app.core.logger import setup_logger

logger = setup_logger(__name__)


async def blog_exception_handler(request: Request, exc: BlogException):
    """Handle custom blog exceptions."""
    logger.warning(
        f"BlogException: {exc.__class__.__name__} - {exc.detail}",
        extra={"path": request.url.path, "method": request.method}
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.__class__.__name__,
            "detail": exc.detail,
            "path": request.url.path
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": " -> ".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })

    logger.warning(
        f"Validation error on {request.url.path}",
        extra={"errors": errors}
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "ValidationError",
            "detail": "Request validation failed",
            "errors": errors,
            "path": request.url.path
        }
    )


async def database_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle SQLAlchemy database errors."""
    logger.error(
        f"Database error: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "DatabaseError",
            "detail": "A database error occurred",
            "path": request.url.path
        }
    )


async def cache_exception_handler(request: Request, exc: RedisError):
    """Handle Redis cache errors."""
    logger.error(
        f"Cache error: {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True
    )

    # Don't fail the request, just log the cache error
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "CacheError",
            "detail": "Cache operation failed, but request was processed",
            "path": request.url.path
        }
    )


async def generic_exception_handler(request: Request, exc: Exception):
    """Handle any unhandled exceptions."""
    logger.error(
        f"Unhandled exception: {exc.__class__.__name__} - {str(exc)}",
        extra={"path": request.url.path},
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred",
            "path": request.url.path
        }
    )


def setup_exception_handlers(app):
    """Register all exception handlers."""
    app.add_exception_handler(BlogException, blog_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(SQLAlchemyError, database_exception_handler)
    app.add_exception_handler(RedisError, cache_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)

    logger.info("✅ Exception handlers registered")