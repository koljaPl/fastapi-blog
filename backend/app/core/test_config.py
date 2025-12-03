"""
Test configuration for switching to SQLite and Redis mock.
Manages test database and cache setup.
"""
import os
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fakeredis import FakeRedis

from app.database import Base
from app.config import settings

# Test database URL (SQLite in memory)
TEST_DATABASE_URL = "sqlite:///./test.db"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)

# Test session factory
TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine
)

# Fake Redis instance for testing
fake_redis = FakeRedis(decode_responses=True)


def get_test_db() -> Generator[Session, None, None]:
    """
    Get test database session.
    Creates tables before each test.
    """
    # Create tables
    Base.metadata.create_all(bind=test_engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_test_redis():
    """
    Get fake Redis instance for testing.
    """
    return fake_redis


def setup_test_db():
    """
    Setup test database.
    Creates all tables.
    """
    Base.metadata.create_all(bind=test_engine)


def teardown_test_db():
    """
    Teardown test database.
    Drops all tables.
    """
    Base.metadata.drop_all(bind=test_engine)


def clear_test_db():
    """
    Clear all data from test database.
    Useful between tests.
    """
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)


def clear_test_redis():
    """
    Clear all data from fake Redis.
    """
    fake_redis.flushall()


class TestMode:
    """
    Context manager for test mode.
    Automatically sets up and tears down test environment.
    """

    def __enter__(self):
        """Setup test environment."""
        setup_test_db()
        clear_test_redis()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup test environment."""
        teardown_test_db()
        clear_test_redis()


# Environment variable to enable test mode
def is_test_mode() -> bool:
    """Check if running in test mode."""
    return os.getenv("TESTING", "false").lower() == "true"