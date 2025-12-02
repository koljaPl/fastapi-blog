"""
Main FastAPI application - improved version.
Production-ready with error handling, monitoring, and security.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import time

from app.api import auth, posts, users
from app.config import settings
from app.core.logger import setup_logger
from app.core.error_handler import setup_exception_handlers
from app.database import check_db_connection, DatabaseManager

# Initialize logger
logger = setup_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A modern, secure, and performant blog platform API",
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# Setup exception handlers
setup_exception_handlers(app)


# Middleware for request timing
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted host middleware (prevent host header attacks)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure with your domain
    )

# Prometheus metrics
if settings.ENABLE_METRICS:
    Instrumentator().instrument(app).expose(app)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(posts.router, prefix="/api/posts", tags=["Posts"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT,
        "docs": "/docs" if not settings.is_production else "disabled in production"
    }


@app.get("/health")
async def health_check():
    """
    Comprehensive health check.
    Checks database and cache connections.
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }

    # Check database
    try:
        db_health = await DatabaseManager.health_check()
        health_status["checks"]["database"] = db_health
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Check Redis
    try:
        from app.dependencies import get_redis
        redis = get_redis()
        redis.ping()
        health_status["checks"]["cache"] = {"status": "healthy"}
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["cache"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    status_code = 200 if health_status["status"] == "healthy" else 503
    return JSONResponse(content=health_status, status_code=status_code)


@app.get("/metrics/stats")
async def get_stats():
    """Get application statistics."""
    return {
        "database": DatabaseManager.get_stats(),
        "environment": settings.ENVIRONMENT,
        "debug": settings.DEBUG,
    }


@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("=" * 50)
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION} starting up...")
    logger.info(f"📊 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Debug mode: {settings.DEBUG}")

    # Check database connection
    if check_db_connection():
        logger.info("✅ Database connection verified")
    else:
        logger.error("❌ Database connection failed")

    # Check Redis
    try:
        from app.dependencies import get_redis
        redis = get_redis()
        redis.ping()
        logger.info("✅ Redis connection verified")
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")

    logger.info(f"📊 Metrics available at /metrics")
    if not settings.is_production:
        logger.info(f"📖 API docs available at /docs")
    logger.info("=" * 50)


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("👋 Application shutting down...")

    # Cleanup
    try:
        DatabaseManager.dispose_pool()
        logger.info("✅ Database pool disposed")
    except Exception as e:
        logger.error(f"Error disposing database pool: {e}")

    logger.info("Goodbye! 👋")


# Error handlers for specific HTTP errors
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "NotFound",
            "detail": "The requested resource was not found",
            "path": request.url.path
        }
    )


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(f"Internal server error on {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "An internal server error occurred",
            "path": request.url.path
        }
    )