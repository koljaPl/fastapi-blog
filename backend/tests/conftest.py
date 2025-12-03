"""
Pytest configuration and fixtures.
Provides reusable test fixtures for all tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.dependencies import get_redis
from app.core.test_config import (
    get_test_db,
    get_test_redis,
    setup_test_db,
    teardown_test_db,
    clear_test_db,
    clear_test_redis
)
from app.models.user import User
from app.models.post import Post, Comment
from app.core.security import hash_password

# Override dependencies
app.dependency_overrides[get_db] = get_test_db
app.dependency_overrides[get_redis] = get_test_redis


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment once for all tests."""
    setup_test_db()
    yield
    teardown_test_db()


@pytest.fixture(autouse=True)
def clear_database():
    """Clear database before each test."""
    clear_test_db()
    clear_test_redis()
    yield


@pytest.fixture
def client():
    """
    Test client fixture.
    Provides FastAPI TestClient for making requests.
    """
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    """
    Database session fixture.
    Provides database session for direct DB operations.
    """
    db = next(get_test_db())
    yield db
    db.close()


@pytest.fixture
def test_user(db: Session):
    """
    Create a test user.
    Returns created user object.
    """
    user = User(
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("Test123456"),
        full_name="Test User",
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_superuser(db: Session):
    """
    Create a test superuser.
    Returns created superuser object.
    """
    user = User(
        email="admin@example.com",
        username="admin",
        hashed_password=hash_password("Admin123456"),
        full_name="Admin User",
        is_active=True,
        is_superuser=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def test_user_token(client: TestClient, test_user: User):
    """
    Get access token for test user.
    Returns token string.
    """
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": test_user.email,
            "password": "Test123456"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def test_superuser_token(client: TestClient, test_superuser: User):
    """
    Get access token for test superuser.
    Returns token string.
    """
    response = client.post(
        "/api/v1/auth/login",
        data={
            "username": test_superuser.email,
            "password": "Admin123456"
        }
    )
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(test_user_token: str):
    """
    Get authorization headers with token.
    Returns headers dict.
    """
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture
def admin_headers(test_superuser_token: str):
    """
    Get authorization headers for admin.
    Returns headers dict.
    """
    return {"Authorization": f"Bearer {test_superuser_token}"}


@pytest.fixture
def test_post(db: Session, test_user: User):
    """
    Create a test post.
    Returns created post object.
    """
    post = Post(
        title="Test Post",
        slug="test-post",
        content="This is test post content.",
        excerpt="Test excerpt",
        published=True,
        author_id=test_user.id
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture
def test_unpublished_post(db: Session, test_user: User):
    """
    Create an unpublished test post.
    Returns created post object.
    """
    post = Post(
        title="Unpublished Post",
        slug="unpublished-post",
        content="This is unpublished content.",
        excerpt="Unpublished excerpt",
        published=False,
        author_id=test_user.id
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post


@pytest.fixture
def test_comment(db: Session, test_post: Post, test_user: User):
    """
    Create a test comment.
    Returns created comment object.
    """
    comment = Comment(
        content="This is a test comment",
        post_id=test_post.id,
        author_id=test_user.id
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@pytest.fixture
def multiple_posts(db: Session, test_user: User):
    """
    Create multiple test posts.
    Returns list of created posts.
    """
    posts = []
    for i in range(5):
        post = Post(
            title=f"Test Post {i}",
            slug=f"test-post-{i}",
            content=f"Content for post {i}",
            excerpt=f"Excerpt {i}",
            published=True,
            author_id=test_user.id,
            views=i * 10
        )
        db.add(post)
        posts.append(post)

    db.commit()
    for post in posts:
        db.refresh(post)

    return posts


# Pytest configuration
def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "auth: mark test as requiring authentication"
    )
    config.addinivalue_line(
        "markers", "admin: mark test as requiring admin privileges"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )