"""
Authentication tests with 90%+ coverage.
Tests all auth endpoints and edge cases.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User


class TestRegistration:
    """Test user registration."""

    def test_register_success(self, client: TestClient):
        """Test successful registration."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@example.com",
                "username": "newuser",
                "password": "NewUser123",
                "full_name": "New User"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with duplicate email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": test_user.email,
                "username": "different",
                "password": "Test123456"
            }
        )

        assert response.status_code == 422
        assert "email" in response.json()["detail"].lower()

    def test_register_duplicate_username(self, client: TestClient, test_user: User):
        """Test registration with duplicate username."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "different@example.com",
                "username": test_user.username,
                "password": "Test123456"
            }
        )

        assert response.status_code == 422
        assert "username" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "not-an-email",
                "username": "testuser",
                "password": "Test123456"
            }
        )

        assert response.status_code == 422

    def test_register_weak_password(self, client: TestClient):
        """Test registration with weak password."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "weak"
            }
        )

        assert response.status_code == 422

    def test_register_short_username(self, client: TestClient):
        """Test registration with short username."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "ab",
                "password": "Test123456"
            }
        )

        assert response.status_code == 422


class TestLogin:
    """Test user login."""

    def test_login_with_email(self, client: TestClient, test_user: User):
        """Test login with email."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123456"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "user" in data

    def test_login_with_username(self, client: TestClient, test_user: User):
        """Test login with username."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.username,
                "password": "Test123456"
            }
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        """Test login with wrong password."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "WrongPassword"
            }
        )

        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@example.com",
                "password": "Test123456"
            }
        )

        assert response.status_code == 401

    def test_login_inactive_user(self, client: TestClient, test_user: User, db: Session):
        """Test login with inactive user."""
        test_user.is_active = False
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123456"
            }
        )

        assert response.status_code == 422


class TestTokenOperations:
    """Test token operations."""

    def test_refresh_token(self, client: TestClient, test_user: User):
        """Test refresh token."""
        # Login first
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": test_user.email,
                "password": "Test123456"
            }
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client: TestClient):
        """Test refresh with invalid token."""
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid_token"}
        )

        assert response.status_code == 401

    def test_verify_token(self, client: TestClient, auth_headers: dict):
        """Test token verification."""
        response = client.get(
            "/api/v1/auth/verify-token",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "id" in response.json()

    def test_verify_invalid_token(self, client: TestClient):
        """Test verification with invalid token."""
        response = client.get(
            "/api/v1/auth/verify-token",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401


class TestPasswordOperations:
    """Test password operations."""

    def test_password_change_success(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test successful password change."""
        response = client.post(
            "/api/v1/auth/password-change",
            headers=auth_headers,
            json={
                "current_password": "Test123456",
                "new_password": "NewPassword123"
            }
        )

        assert response.status_code == 200

    def test_password_change_wrong_current(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test password change with wrong current password."""
        response = client.post(
            "/api/v1/auth/password-change",
            headers=auth_headers,
            json={
                "current_password": "WrongPassword",
                "new_password": "NewPassword123"
            }
        )

        assert response.status_code == 422

    def test_password_change_weak_new(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test password change with weak new password."""
        response = client.post(
            "/api/v1/auth/password-change",
            headers=auth_headers,
            json={
                "current_password": "Test123456",
                "new_password": "weak"
            }
        )

        assert response.status_code == 422

    def test_password_change_same_password(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test password change with same password."""
        response = client.post(
            "/api/v1/auth/password-change",
            headers=auth_headers,
            json={
                "current_password": "Test123456",
                "new_password": "Test123456"
            }
        )

        assert response.status_code == 422

    def test_password_reset_request(self, client: TestClient, test_user: User):
        """Test password reset request."""
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": test_user.email}
        )

        assert response.status_code == 200
        assert "message" in response.json()

    def test_password_reset_request_nonexistent(self, client: TestClient):
        """Test password reset for nonexistent email."""
        response = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nonexistent@example.com"}
        )

        # Should still return success to prevent email enumeration
        assert response.status_code == 200


class TestLogout:
    """Test logout."""

    def test_logout_success(self, client: TestClient, auth_headers: dict):
        """Test successful logout."""
        response = client.post(
            "/api/v1/auth/logout",
            headers=auth_headers
        )

        assert response.status_code == 200
        assert "message" in response.json()

    def test_logout_without_auth(self, client: TestClient):
        """Test logout without authentication."""
        response = client.post("/api/v1/auth/logout")

        assert response.status_code == 403


class TestAuthenticationRequired:
    """Test authentication requirements."""

    def test_protected_endpoint_without_token(self, client: TestClient):
        """Test accessing protected endpoint without token."""
        response = client.get("/api/v1/users/me")

        assert response.status_code == 403

    def test_protected_endpoint_with_invalid_token(self, client: TestClient):
        """Test accessing protected endpoint with invalid token."""
        response = client.get(
            "/api/v1/users/me",
            headers={"Authorization": "Bearer invalid_token"}
        )

        assert response.status_code == 401

    def test_protected_endpoint_with_valid_token(
        self,
        client: TestClient,
        auth_headers: dict
    ):
        """Test accessing protected endpoint with valid token."""
        response = client.get(
            "/api/v1/users/me",
            headers=auth_headers
        )

        assert response.status_code == 200