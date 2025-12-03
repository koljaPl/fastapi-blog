"""
Database connection and session management.
Optimized with connection pooling.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

from app.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

# Create engine with connection pooling
engine = create_engine(
    settings.DATABASE_URL,
    poolclass=QueuePool,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    pool_recycle=3600,  # Recycle connections after 1 hour
    echo=settings.DB_ECHO,
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for models
Base = declarative_base()


# Event listeners for better debugging
@event.listens_for(engine, "connect")
def receive_connect(dbapi_conn, connection_record):
    """Log when connection is created."""
    logger.debug("Database connection established")


@event.listens_for(engine, "checkout")
def receive_checkout(dbapi_conn, connection_record, connection_proxy):
    """Log when connection is checked out from pool."""
    logger.debug("Database connection checked out from pool")


@event.listens_for(engine, "checkin")
def receive_checkin(dbapi_conn, connection_record):
    """Log when connection is returned to pool."""
    logger.debug("Database connection returned to pool")


def get_db():
    """
    Dependency to get database session.
    Automatically closes session after request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context():
    """
    Context manager for database session.
    Use in background tasks or scripts.

    Example:
        with get_db_context() as db:
            user = db.query(User).first()
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """
    Initialize database.
    Create all tables if they don't exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise


def check_db_connection() -> bool:
    """
    Check if database connection is working.

    Returns:
        True if connection successful
    """
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
        logger.info("✅ Database connection verified")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        return False


class DatabaseManager:
    """Helper class for database operations."""

    @staticmethod
    def get_stats() -> dict:
        """Get database connection pool statistics."""
        pool = engine.pool
        return {
            "pool_size": pool.size(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "queue_size": pool.queue_size if hasattr(pool, 'queue_size') else 0,
        }

    @staticmethod
    def dispose_pool():
        """Dispose of all connections in the pool."""
        engine.dispose()
        logger.info("Database connection pool disposed")

    @staticmethod
    async def health_check() -> dict:
        """
        Perform health check on database.

        Returns:
            Health status dict
        """
        try:
            with engine.connect() as conn:
                result = conn.execute("SELECT version()")
                version = result.scalar()

            stats = DatabaseManager.get_stats()

            return {
                "status": "healthy",
                "version": version,
                "pool": stats
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Import all models here to ensure they're registered with Base
# This allows alembic to auto-generate migrations
from app.models.user import User  # noqa
from app.models.post import Post, Comment  # noqa