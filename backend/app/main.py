"""
Main FastAPI application - Production Ready.
Modern, secure, observable, and performant.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import time

from app.api.v1 import api_router
from app.config import settings
from app.core.logger import setup_logger
from app.core.error_handler import setup_exception_handlers
from app.database import check_db_connection, DatabaseManager

# Initialize logger
logger = setup_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    Modern way to handle app lifecycle.
    """
    # Startup
    logger.info("=" * 60)
    logger.info(f"🚀 {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"📊 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🔧 Debug: {settings.DEBUG}")
    logger.info("=" * 60)

    # Check database
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

    if settings.ENABLE_METRICS:
        logger.info("📊 Metrics enabled at /metrics")

    if not settings.is_production:
        logger.info("📖 API documentation at /docs")

    logger.info("✨ Application started successfully!")
    logger.info("=" * 60)

    yield

    # Shutdown
    logger.info("=" * 60)
    logger.info("👋 Shutting down application...")

    try:
        DatabaseManager.dispose_pool()
        logger.info("✅ Database pool disposed")
    except Exception as e:
        logger.error(f"❌ Error disposing database pool: {e}")

    logger.info("✨ Shutdown complete. Goodbye!")
    logger.info("=" * 60)


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    ## Modern Blog Platform API
    
    A secure, performant, and well-documented blog platform.
    
    ### Features:
    - 🔐 **Secure Authentication**: JWT-based with refresh tokens
    - 📝 **Blog Posts**: Full CRUD with search and filters
    - 💬 **Comments**: Interactive commenting system
    - 👥 **User Management**: Profiles and permissions
    - 🚀 **High Performance**: Redis caching and optimized queries
    - 📊 **Observable**: Prometheus metrics and structured logging
    
    ### Quick Start:
    1. Register a new account at `/api/v1/auth/register`
    2. Login to get access token at `/api/v1/auth/login`
    3. Use the token in Authorization header: `Bearer <token>`
    
    ### Rate Limits:
    - Default: 100 requests per minute
    - Authenticated users: Higher limits
    """,
    version=settings.APP_VERSION,
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
    lifespan=lifespan,
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "User authentication and authorization"
        },
        {
            "name": "Posts",
            "description": "Blog post management"
        },
        {
            "name": "Users",
            "description": "User profile operations"
        },
        {
            "name": "Comments",
            "description": "Comment system"
        },
        {
            "name": "Health",
            "description": "Health checks and monitoring"
        }
    ]
)

# Setup exception handlers
setup_exception_handlers(app)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    """Add processing time to response headers."""
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.4f}"
    return response


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests."""
    logger.info(
        f"→ {request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "client": request.client.host if request.client else "unknown"
        }
    )

    response = await call_next(request)

    logger.info(
        f"← {request.method} {request.url.path} - {response.status_code}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code
        }
    )

    return response


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Process-Time", "X-Total-Count"],
)

# Gzip compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Trusted host (production)
if settings.is_production:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure with your domain
    )

# Prometheus metrics
if settings.ENABLE_METRICS:
    Instrumentator().instrument(app).expose(app)

# Include API v1 router
app.include_router(
    api_router,
    prefix="/api/v1"
)


# Root endpoint
@app.get(
    "/",
    tags=["Health"],
    summary="API Info",
    description="Get basic API information"
)
async def root():
    """API root endpoint with basic information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "status": "running",
        "docs": "/docs" if not settings.is_production else "disabled",
        "health": "/health",
        "api_v1": "/api/v1"
    }


# Health check
@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Comprehensive health check for all services"
)
async def health_check():
    """
    Comprehensive health check.
    Returns status of all critical services.
    """
    health_status = {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }

    # Database check
    try:
        db_health = await DatabaseManager.health_check()
        health_status["checks"]["database"] = db_health
        if db_health["status"] != "healthy":
            health_status["status"] = "degraded"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["checks"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }

    # Redis check
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

    # Determine status code
    status_code = status.HTTP_200_OK if health_status["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(content=health_status, status_code=status_code)


# Readiness probe (Kubernetes)
@app.get(
    "/ready",
    tags=["Health"],
    summary="Readiness Probe",
    description="Check if app is ready to serve requests"
)
async def readiness_check():
    """Check if app is ready (for Kubernetes)."""
    try:
        # Quick database check
        if not check_db_connection():
            return JSONResponse(
                content={"ready": False, "reason": "Database not ready"},
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        return {"ready": True}
    except Exception as e:
        return JSONResponse(
            content={"ready": False, "reason": str(e)},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE
        )


# Liveness probe (Kubernetes)
@app.get(
    "/alive",
    tags=["Health"],
    summary="Liveness Probe",
    description="Check if app is alive"
)
async def liveness_check():
    """Check if app is alive (for Kubernetes)."""
    return {"alive": True}


# Metrics endpoint info
@app.get(
    "/metrics/info",
    tags=["Health"],
    summary="Metrics Info",
    description="Information about available metrics"
)
async def metrics_info():
    """Get information about metrics."""
    return {
        "prometheus": "/metrics" if settings.ENABLE_METRICS else "disabled",
        "database": DatabaseManager.get_stats(),
        "environment": settings.ENVIRONMENT,
        "features": {
            "caching": True,
            "rate_limiting": settings.RATE_LIMIT_ENABLED,
            "monitoring": settings.ENABLE_METRICS
        }
    }


# Custom 404 handler
@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 errors with helpful message."""
    return JSONResponse(
        status_code=404,
        content={
            "error": "NotFound",
            "detail": f"The endpoint {request.url.path} does not exist",
            "path": request.url.path,
            "available_endpoints": {
                "docs": "/docs" if not settings.is_production else None,
                "health": "/health",
                "api": "/api/v1"
            }
        }
    )


# Custom 500 handler
@app.exception_handler(500)
async def internal_error_handler(request: Request, exc):
    """Handle 500 errors."""
    logger.error(
        f"Internal server error on {request.url.path}: {exc}",
        exc_info=True
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "detail": "An unexpected error occurred. Please try again later.",
            "path": request.url.path
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )