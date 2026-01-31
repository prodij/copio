"""Tests for authentication endpoints."""

import pytest
import uuid
from httpx import AsyncClient


def unique_slug() -> str:
    """Generate a unique slug for testing."""
    return f"test-{uuid.uuid4().hex[:8]}"


def unique_email(prefix: str = "test") -> str:
    """Generate a unique email for testing."""
    return f"{prefix}-{uuid.uuid4().hex[:8]}@test.com"


class TestTenantRegistration:
    """Tests for tenant registration endpoint."""

    async def test_register_tenant_success(self, client: AsyncClient):
        """Test successful tenant registration."""
        slug = unique_slug()
        email = unique_email("admin")
        
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Test Company",
                "tenant_slug": slug,
                "email": email,
                "password": "securepassword123",
                "first_name": "John",
                "last_name": "Doe",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_slug"] == slug
        assert data["email"] == email
        assert "tenant_id" in data
        assert "user_id" in data

    async def test_register_tenant_duplicate_slug(self, client: AsyncClient):
        """Test duplicate tenant slug is rejected."""
        slug = unique_slug()
        
        # First registration
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "First Company",
                "tenant_slug": slug,
                "email": unique_email("first"),
                "password": "password123",
            },
        )
        
        # Second registration with same slug
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Second Company",
                "tenant_slug": slug,
                "email": unique_email("second"),
                "password": "password123",
            },
        )
        
        assert response.status_code == 409
        assert "slug" in response.json()["detail"].lower()

    async def test_register_tenant_duplicate_email(self, client: AsyncClient):
        """Test duplicate email is rejected."""
        email = unique_email("dup")
        
        # First registration
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "First Company",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "password123",
            },
        )
        
        # Second registration with same email
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Second Company",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "password123",
            },
        )
        
        assert response.status_code == 409
        assert "email" in response.json()["detail"].lower()


class TestLogin:
    """Tests for login endpoint."""

    async def test_login_success(self, client: AsyncClient):
        """Test successful login."""
        email = unique_email("login")
        
        # Register first
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Login Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "loginpassword123",
            },
        )
        
        # Login
        response = await client.post(
            "/api/v1/auth/login",
            data={  # form data, not json
                "username": email,
                "password": "loginpassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient):
        """Test login with invalid credentials."""
        response = await client.post(
            "/api/v1/auth/login",
            data={
                "username": "nonexistent@test.com",
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code == 400


class TestCurrentUser:
    """Tests for /me endpoint."""

    async def test_get_current_user(self, client: AsyncClient):
        """Test getting current user info."""
        email = unique_email("me")
        
        # Register and login
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Me Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "mepassword123",
                "first_name": "Me",
                "last_name": "User",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "mepassword123"},
        )
        token = login_response.json()["access_token"]
        
        # Get /me
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == email
        assert data["first_name"] == "Me"
        assert data["role"] == "admin"

    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test /me without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestProfileUpdate:
    """Tests for profile update endpoint."""

    async def test_update_profile(self, client: AsyncClient):
        """Test updating user profile."""
        email = unique_email("profile")
        
        # Setup: register and login
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Profile Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "profilepass123",
                "first_name": "Old",
                "last_name": "Name",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "profilepass123"},
        )
        token = login_response.json()["access_token"]
        
        # Update profile
        response = await client.patch(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"first_name": "New", "last_name": "Updated"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["first_name"] == "New"
        assert data["last_name"] == "Updated"


class TestChangePassword:
    """Tests for password change endpoint."""

    async def test_change_password_success(self, client: AsyncClient):
        """Test successful password change."""
        email = unique_email("chpwd")
        
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Password Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "oldpassword123",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "oldpassword123"},
        )
        token = login_response.json()["access_token"]
        
        # Change password
        response = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "oldpassword123",
                "new_password": "newpassword456",
            },
        )
        
        assert response.status_code == 200
        
        # Verify can login with new password
        new_login = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "newpassword456"},
        )
        assert new_login.status_code == 200

    async def test_change_password_wrong_current(self, client: AsyncClient):
        """Test password change with wrong current password."""
        email = unique_email("wrongpwd")
        
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Wrong Pass Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "correctpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "correctpassword"},
        )
        token = login_response.json()["access_token"]
        
        # Try to change with wrong current password
        response = await client.post(
            "/api/v1/auth/change-password",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "current_password": "wrongcurrent",
                "new_password": "newpassword456",
            },
        )
        
        assert response.status_code == 400


class TestUserInvite:
    """Tests for user invitation endpoints."""

    async def test_invite_and_accept(self, client: AsyncClient):
        """Test full invite flow."""
        admin_email = unique_email("admin")
        invited_email = unique_email("invited")
        
        # Setup: register admin
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Invite Test",
                "tenant_slug": unique_slug(),
                "email": admin_email,
                "password": "adminpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "adminpassword"},
        )
        token = login_response.json()["access_token"]
        
        # Invite user
        invite_response = await client.post(
            "/api/v1/auth/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": invited_email,
                "role": "member",
                "first_name": "Invited",
                "last_name": "User",
            },
        )
        
        assert invite_response.status_code == 200
        invite_data = invite_response.json()
        assert "invite_token" in invite_data
        
        # Accept invite
        accept_response = await client.post(
            "/api/v1/auth/accept-invite",
            json={
                "token": invite_data["invite_token"],
                "password": "invitedpassword123",
            },
        )
        
        assert accept_response.status_code == 200
        
        # Verify invited user can login
        invited_login = await client.post(
            "/api/v1/auth/login",
            data={"username": invited_email, "password": "invitedpassword123"},
        )
        assert invited_login.status_code == 200

    async def test_invite_requires_admin(self, client: AsyncClient):
        """Test that non-admins cannot invite users."""
        admin_email = unique_email("admin")
        member_email = unique_email("member")
        
        # Setup: create admin and member
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Role Test",
                "tenant_slug": unique_slug(),
                "email": admin_email,
                "password": "adminpassword",
            },
        )
        
        admin_login = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "adminpassword"},
        )
        admin_token = admin_login.json()["access_token"]
        
        # Create member via admin
        await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": member_email,
                "password": "memberpassword",
                "role": "member",
            },
        )
        
        # Login as member
        member_login = await client.post(
            "/api/v1/auth/login",
            data={"username": member_email, "password": "memberpassword"},
        )
        member_token = member_login.json()["access_token"]
        
        # Try to invite as member (should fail)
        response = await client.post(
            "/api/v1/auth/invite",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"email": unique_email("another")},
        )
        
        assert response.status_code == 403


class TestCreateUser:
    """Tests for direct user creation endpoint."""

    async def test_create_user_as_admin(self, client: AsyncClient):
        """Test admin can create users directly."""
        admin_email = unique_email("admin")
        created_email = unique_email("created")
        
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Create Test",
                "tenant_slug": unique_slug(),
                "email": admin_email,
                "password": "adminpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": admin_email, "password": "adminpassword"},
        )
        token = login_response.json()["access_token"]
        
        # Create user
        response = await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": created_email,
                "password": "createdpassword123",
                "role": "member",
                "first_name": "Created",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == created_email
        assert data["role"] == "member"
        
        # Verify user can login
        user_login = await client.post(
            "/api/v1/auth/login",
            data={"username": created_email, "password": "createdpassword123"},
        )
        assert user_login.status_code == 200


class TestDeactivateAccount:
    """Tests for account deactivation."""

    async def test_deactivate_account(self, client: AsyncClient):
        """Test user can deactivate their own account."""
        email = unique_email("deactivate")
        
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Deactivate Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "deactivatepass",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "deactivatepass"},
        )
        token = login_response.json()["access_token"]
        
        # Deactivate
        response = await client.delete(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        
        # Verify cannot login anymore
        failed_login = await client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": "deactivatepass"},
        )
        assert failed_login.status_code == 400


class TestForgotPassword:
    """Tests for forgot password flow."""

    async def test_forgot_password_request(self, client: AsyncClient):
        """Test forgot password request."""
        email = unique_email("forgot")
        
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Forgot Test",
                "tenant_slug": unique_slug(),
                "email": email,
                "password": "forgotpassword",
            },
        )
        
        # Request reset
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": email},
        )
        
        assert response.status_code == 200
        # Should always return success (doesn't reveal if email exists)
        assert "message" in response.json()

    async def test_forgot_password_nonexistent_email(self, client: AsyncClient):
        """Test forgot password with non-existent email returns success."""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": unique_email("nonexistent")},
        )
        
        # Should return 200 to not reveal email existence
        assert response.status_code == 200
