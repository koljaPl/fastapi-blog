"""
Tests for users and comments endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.post import Post, Comment


class TestUsers:
    """Test user endpoints."""

    def test_get_current_user(self, client: TestClient, auth_headers: dict):
        """Test getting current user profile."""
        response = client.get("/api/v1/users/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "username" in data

    def test_update_user_profile(self, client: TestClient, auth_headers: dict):
        """Test updating user profile."""
        response = client.put(
            "/api/v1/users/me",
            headers=auth_headers,
            json={
                "full_name": "Updated Name",
                "bio": "New bio"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["full_name"] == "Updated Name"
        assert data["bio"] == "New bio"

    def test_get_user_by_id(self, client: TestClient, test_user: User):
        """Test getting user by ID."""
        response = client.get(f"/api/v1/users/{test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == test_user.id

    def test_get_user_by_username(self, client: TestClient, test_user: User):
        """Test getting user by username."""
        response = client.get(f"/api/v1/users/username/{test_user.username}")

        assert response.status_code == 200
        data = response.json()
        assert data["username"] == test_user.username

    def test_get_user_posts(
            self,
            client: TestClient,
            test_user: User,
            multiple_posts: list
    ):
        """Test getting user's posts."""
        response = client.get(f"/api/v1/users/{test_user.id}/posts")

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_get_my_posts(
            self,
            client: TestClient,
            auth_headers: dict,
            multiple_posts: list
    ):
        """Test getting own posts."""
        response = client.get("/api/v1/users/me/posts", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) > 0

    def test_delete_account(
            self,
            client: TestClient,
            auth_headers: dict,
            test_user: User,
            db: Session
    ):
        """Test account deletion."""
        response = client.delete("/api/v1/users/me", headers=auth_headers)

        assert response.status_code == 204

        # Verify user is deactivated
        db.refresh(test_user)
        assert test_user.is_active is False

    def test_list_users_admin_only(
            self,
            client: TestClient,
            auth_headers: dict
    ):
        """Test that regular users can't list all users."""
        response = client.get("/api/v1/users", headers=auth_headers)

        assert response.status_code == 403

    def test_list_users_as_admin(
            self,
            client: TestClient,
            admin_headers: dict,
            test_user: User
    ):
        """Test listing users as admin."""
        response = client.get("/api/v1/users", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "users" in data
        assert data["total"] > 0

    def test_activate_user_admin(
            self,
            client: TestClient,
            admin_headers: dict,
            test_user: User,
            db: Session
    ):
        """Test activating user as admin."""
        # Deactivate first
        test_user.is_active = False
        db.commit()

        response = client.patch(
            f"/api/v1/users/{test_user.id}/activate",
            headers=admin_headers
        )

        assert response.status_code == 200
        db.refresh(test_user)
        assert test_user.is_active is True

    def test_deactivate_user_admin(
            self,
            client: TestClient,
            admin_headers: dict,
            test_user: User,
            db: Session
    ):
        """Test deactivating user as admin."""
        response = client.patch(
            f"/api/v1/users/{test_user.id}/deactivate",
            headers=admin_headers
        )

        assert response.status_code == 200
        db.refresh(test_user)
        assert test_user.is_active is False


class TestComments:
    """Test comment endpoints."""

    def test_get_post_comments(
            self,
            client: TestClient,
            test_post: Post,
            test_comment: Comment
    ):
        """Test getting comments for a post."""
        response = client.get(f"/api/v1/comments/post/{test_post.id}")

        assert response.status_code == 200
        data = response.json()
        assert "comments" in data
        assert len(data["comments"]) == 1

    def test_get_post_comments_empty(self, client: TestClient, test_post: Post):
        """Test getting comments when none exist."""
        response = client.get(f"/api/v1/comments/post/{test_post.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["comments"] == []
        assert data["total"] == 0

    def test_create_comment_success(
            self,
            client: TestClient,
            test_post: Post,
            auth_headers: dict
    ):
        """Test creating a comment."""
        response = client.post(
            f"/api/v1/comments/post/{test_post.id}",
            headers=auth_headers,
            json={"content": "Great post!"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["content"] == "Great post!"
        assert data["post_id"] == test_post.id

    def test_create_comment_without_auth(
            self,
            client: TestClient,
            test_post: Post
    ):
        """Test creating comment without authentication."""
        response = client.post(
            f"/api/v1/comments/post/{test_post.id}",
            json={"content": "Comment"}
        )

        assert response.status_code == 403

    def test_create_comment_empty_content(
            self,
            client: TestClient,
            test_post: Post,
            auth_headers: dict
    ):
        """Test creating comment with empty content."""
        response = client.post(
            f"/api/v1/comments/post/{test_post.id}",
            headers=auth_headers,
            json={"content": ""}
        )

        assert response.status_code == 422

    def test_create_comment_on_unpublished_post(
            self,
            client: TestClient,
            test_unpublished_post: Post,
            auth_headers: dict
    ):
        """Test creating comment on unpublished post."""
        response = client.post(
            f"/api/v1/comments/post/{test_unpublished_post.id}",
            headers=auth_headers,
            json={"content": "Comment"}
        )

        assert response.status_code == 422

    def test_update_comment_success(
            self,
            client: TestClient,
            test_comment: Comment,
            auth_headers: dict
    ):
        """Test updating own comment."""
        response = client.put(
            f"/api/v1/comments/{test_comment.id}",
            headers=auth_headers,
            json={"content": "Updated comment"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Updated comment"

    def test_update_comment_not_owner(
            self,
            client: TestClient,
            test_comment: Comment,
            db: Session
    ):
        """Test updating comment by non-owner."""
        # Create another user
        other_user = User(
            email="other@example.com",
            username="otheruser",
            hashed_password="hashed",
            is_active=True
        )
        db.add(other_user)
        db.commit()

        # Register and login as other user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "other3@example.com",
                "username": "other3",
                "password": "Other123456"
            }
        )

        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "other3@example.com",
                "password": "Other123456"
            }
        )
        other_token = login_response.json()["access_token"]

        # Try to update
        response = client.put(
            f"/api/v1/comments/{test_comment.id}",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"content": "Hacked"}
        )

        assert response.status_code == 403

    def test_delete_comment_success(
            self,
            client: TestClient,
            test_comment: Comment,
            auth_headers: dict,
            db: Session
    ):
        """Test deleting own comment."""
        comment_id = test_comment.id

        response = client.delete(
            f"/api/v1/comments/{comment_id}",
            headers=auth_headers
        )

        assert response.status_code == 204

        # Verify deleted
        deleted = db.query(Comment).filter(Comment.id == comment_id).first()
        assert deleted is None

    def test_get_user_comments(
            self,
            client: TestClient,
            test_user: User,
            test_comment: Comment
    ):
        """Test getting all comments by a user."""
        response = client.get(f"/api/v1/comments/user/{test_user.id}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_get_my_comments(
            self,
            client: TestClient,
            auth_headers: dict,
            test_comment: Comment
    ):
        """Test getting own comments."""
        response = client.get(
            "/api/v1/comments/me/my-comments",
            headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1

    def test_comment_pagination(
            self,
            client: TestClient,
            test_post: Post,
            test_user: User,
            db: Session
    ):
        """Test comment pagination."""
        # Create multiple comments
        for i in range(15):
            comment = Comment(
                content=f"Comment {i}",
                post_id=test_post.id,
                author_id=test_user.id
            )
            db.add(comment)
        db.commit()

        response = client.get(
            f"/api/v1/comments/post/{test_post.id}?skip=0&limit=10"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["comments"]) == 10
        assert data["total"] == 15
        assert data["has_more"] is True


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_root_endpoint(self, client: TestClient):
        """Test root endpoint."""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data

    def test_health_check(self, client: TestClient):
        """Test health check endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_readiness_probe(self, client: TestClient):
        """Test readiness probe."""
        response = client.get("/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True

    def test_liveness_probe(self, client: TestClient):
        """Test liveness probe."""
        response = client.get("/alive")

        assert response.status_code == 200
        data = response.json()
        assert data["alive"] is True