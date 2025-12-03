"""
Posts tests with comprehensive coverage.
Tests all post endpoints and scenarios.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.post import Post
from app.models.user import User


class TestListPosts:
    """Test listing posts."""

    def test_list_posts_empty(self, client: TestClient):
        """Test listing when no posts exist."""
        response = client.get("/api/v1/posts")

        assert response.status_code == 200
        data = response.json()
        assert data["posts"] == []
        assert data["total"] == 0

    def test_list_posts_success(self, client: TestClient, multiple_posts: list):
        """Test successful post listing."""
        response = client.get("/api/v1/posts")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 5
        assert data["total"] == 5
        assert data["has_more"] is False

    def test_list_posts_pagination(self, client: TestClient, multiple_posts: list):
        """Test post pagination."""
        response = client.get("/api/v1/posts?skip=0&limit=2")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 2
        assert data["total"] == 5
        assert data["has_more"] is True
        assert data["page"] == 1

    def test_list_posts_search(self, client: TestClient, multiple_posts: list):
        """Test post search."""
        response = client.get("/api/v1/posts?search=Post 1")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 1
        assert "Post 1" in data["posts"][0]["title"]

    def test_list_posts_filter_by_author(
            self,
            client: TestClient,
            test_user: User,
            multiple_posts: list
    ):
        """Test filtering by author."""
        response = client.get(f"/api/v1/posts?author_id={test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 5
        for post in data["posts"]:
            assert post["author_id"] == test_user.id

    def test_list_posts_sort_by_views(self, client: TestClient, multiple_posts: list):
        """Test sorting by views."""
        response = client.get("/api/v1/posts?sort_by=views&sort_order=desc")

        assert response.status_code == 200
        data = response.json()
        # Check that posts are sorted by views descending
        views = [post["views"] for post in data["posts"]]
        assert views == sorted(views, reverse=True)

    def test_list_unpublished_posts_hidden(
            self,
            client: TestClient,
            test_unpublished_post: Post
    ):
        """Test that unpublished posts are hidden."""
        response = client.get("/api/v1/posts")

        assert response.status_code == 200
        data = response.json()
        assert len(data["posts"]) == 0


class TestGetPost:
    """Test getting single post."""

    def test_get_post_success(self, client: TestClient, test_post: Post):
        """Test successful post retrieval."""
        response = client.get(f"/api/v1/posts/{test_post.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_post.id
        assert data["title"] == test_post.title
        assert "content" in data

    def test_get_post_not_found(self, client: TestClient):
        """Test getting nonexistent post."""
        response = client.get("/api/v1/posts/999")

        assert response.status_code == 404

    def test_get_post_by_slug(self, client: TestClient, test_post: Post):
        """Test getting post by slug."""
        response = client.get(f"/api/v1/posts/slug/{test_post.slug}")

        assert response.status_code == 200
        data = response.json()
        assert data["slug"] == test_post.slug

    def test_get_post_increments_views(
            self,
            client: TestClient,
            test_post: Post,
            db: Session
    ):
        """Test that getting post increments views."""
        initial_views = test_post.views

        client.get(f"/api/v1/posts/{test_post.id}")

        db.refresh(test_post)
        assert test_post.views == initial_views + 1

    def test_get_unpublished_post_unauthorized(
            self,
            client: TestClient,
            test_unpublished_post: Post
    ):
        """Test getting unpublished post without auth."""
        response = client.get(f"/api/v1/posts/{test_unpublished_post.id}")

        assert response.status_code == 404

    def test_get_unpublished_post_as_author(
            self,
            client: TestClient,
            test_unpublished_post: Post,
            auth_headers: dict
    ):
        """Test getting own unpublished post."""
        response = client.get(
            f"/api/v1/posts/{test_unpublished_post.id}",
            headers=auth_headers
        )

        assert response.status_code == 200


class TestCreatePost:
    """Test post creation."""

    def test_create_post_success(self, client: TestClient, auth_headers: dict):
        """Test successful post creation."""
        response = client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "New Post",
                "content": "This is new post content with enough text.",
                "excerpt": "Short excerpt",
                "published": True
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["title"] == "New Post"
        assert data["slug"] == "new-post"
        assert data["published"] is True

    def test_create_post_without_auth(self, client: TestClient):
        """Test creating post without authentication."""
        response = client.post(
            "/api/v1/posts",
            json={
                "title": "New Post",
                "content": "Content here"
            }
        )

        assert response.status_code == 403

    def test_create_post_auto_excerpt(self, client: TestClient, auth_headers: dict):
        """Test auto-generated excerpt."""
        response = client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "Post Without Excerpt",
                "content": "This is content that is long enough to generate an excerpt automatically.",
                "published": False
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["excerpt"] is not None
        assert len(data["excerpt"]) > 0

    def test_create_post_short_title(self, client: TestClient, auth_headers: dict):
        """Test creating post with short title."""
        response = client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "Ab",
                "content": "Content here"
            }
        )

        assert response.status_code == 422

    def test_create_post_short_content(self, client: TestClient, auth_headers: dict):
        """Test creating post with short content."""
        response = client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": "Valid Title",
                "content": "Short"
            }
        )

        assert response.status_code == 422

    def test_create_post_unique_slug(
            self,
            client: TestClient,
            auth_headers: dict,
            test_post: Post
    ):
        """Test that duplicate titles get unique slugs."""
        response = client.post(
            "/api/v1/posts",
            headers=auth_headers,
            json={
                "title": test_post.title,
                "content": "Different content here",
                "published": True
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["slug"] != test_post.slug
        assert test_post.slug in data["slug"]


class TestUpdatePost:
    """Test post updates."""

    def test_update_post_success(
            self,
            client: TestClient,
            test_post: Post,
            auth_headers: dict
    ):
        """Test successful post update."""
        response = client.put(
            f"/api/v1/posts/{test_post.id}",
            headers=auth_headers,
            json={
                "title": "Updated Title",
                "published": False
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        assert data["published"] is False

    def test_update_post_without_auth(self, client: TestClient, test_post: Post):
        """Test updating post without authentication."""
        response = client.put(
            f"/api/v1/posts/{test_post.id}",
            json={"title": "Updated"}
        )

        assert response.status_code == 403

    def test_update_post_not_owner(
            self,
            client: TestClient,
            test_post: Post,
            db: Session
    ):
        """Test updating post by non-owner."""
        # Create another user
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="hashed",
            is_active=True
        )
        db.add(other_user)
        db.commit()

        # Login as other user
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "other2@example.com",
                "username": "other2",
                "password": "Other123456"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "other2@example.com",
                "password": "Other123456"
            }
        )
        other_token = login_response.json()["access_token"]

        # Try to update
        response = client.put(
            f"/api/v1/posts/{test_post.id}",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"title": "Hacked"}
        )

        assert response.status_code == 403

    def test_update_post_not_found(self, client: TestClient, auth_headers: dict):
        """Test updating nonexistent post."""
        response = client.put(
            "/api/v1/posts/999",
            headers=auth_headers,
            json={"title": "Updated"}
        )

        assert response.status_code == 404


class TestDeletePost:
    """Test post deletion."""

    def test_delete_post_success(
            self,
            client: TestClient,
            test_post: Post,
            auth_headers: dict,
            db: Session
    ):
        """Test successful post deletion."""
        post_id = test_post.id

        response = client.delete(
            f"/api/v1/posts/{post_id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify post is deleted
        deleted_post = db.query(Post).filter(Post.id == post_id).first()
        assert deleted_post is None

    def test_delete_post_without_auth(self, client: TestClient, test_post: Post):
        """Test deleting post without authentication."""
        response = client.delete(f"/api/v1/posts/{test_post.id}")

        assert response.status_code == 403

    def test_delete_post_not_found(self, client: TestClient, auth_headers: dict):
        """Test deleting nonexistent post."""
        response = client.delete(
            "/api/v1/posts/999",
            headers=auth_headers
        )

        assert response.status_code == 404


class TestPopularPosts:
    """Test popular posts endpoint."""

    def test_get_popular_posts(self, client: TestClient, multiple_posts: list):
        """Test getting popular posts."""
        response = client.get("/api/v1/posts/popular/top?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        # Check sorted by views
        views = [post["views"] for post in data]
        assert views == sorted(views, reverse=True)


class TestRecentPosts:
    """Test recent posts endpoint."""

    def test_get_recent_posts(self, client: TestClient, multiple_posts: list):
        """Test getting recent posts."""
        response = client.get("/api/v1/posts/recent/latest?limit=3")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3