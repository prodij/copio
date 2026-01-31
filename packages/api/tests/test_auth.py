"""Tests for authentication endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.tenant import Tenant
from src.db.models.user import User


class TestTenantRegistration:
    """Tests for tenant registration endpoint."""

    async def test_register_tenant_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful tenant registration."""
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Test Company",
                "tenant_slug": "test-company",
                "email": "admin@test.com",
                "password": "securepassword123",
                "first_name": "John",
                "last_name": "Doe",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["tenant_slug"] == "test-company"
        assert data["email"] == "admin@test.com"
        assert "tenant_id" in data
        assert "user_id" in data

    async def test_register_tenant_duplicate_slug(self, client: AsyncClient, db_session: AsyncSession):
        """Test duplicate tenant slug is rejected."""
        # First registration
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "First Company",
                "tenant_slug": "duplicate-slug",
                "email": "first@test.com",
                "password": "password123",
            },
        )
        
        # Second registration with same slug
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Second Company",
                "tenant_slug": "duplicate-slug",
                "email": "second@test.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 409
        assert "slug" in response.json()["detail"].lower()

    async def test_register_tenant_duplicate_email(self, client: AsyncClient, db_session: AsyncSession):
        """Test duplicate email is rejected."""
        # First registration
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "First Company",
                "tenant_slug": "first-company",
                "email": "same@test.com",
                "password": "password123",
            },
        )
        
        # Second registration with same email
        response = await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Second Company",
                "tenant_slug": "second-company",
                "email": "same@test.com",
                "password": "password123",
            },
        )
        
        assert response.status_code == 409
        assert "email" in response.json()["detail"].lower()


class TestLogin:
    """Tests for login endpoint."""

    async def test_login_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful login."""
        # Register first
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Login Test",
                "tenant_slug": "login-test",
                "email": "login@test.com",
                "password": "loginpassword123",
            },
        )
        
        # Login
        response = await client.post(
            "/api/v1/auth/login",
            data={  # form data, not json
                "username": "login@test.com",
                "password": "loginpassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_invalid_credentials(self, client: AsyncClient, db_session: AsyncSession):
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

    async def test_get_current_user(self, client: AsyncClient, db_session: AsyncSession):
        """Test getting current user info."""
        # Register and login
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Me Test",
                "tenant_slug": "me-test",
                "email": "me@test.com",
                "password": "mepassword123",
                "first_name": "Me",
                "last_name": "User",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "me@test.com", "password": "mepassword123"},
        )
        token = login_response.json()["access_token"]
        
        # Get /me
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@test.com"
        assert data["first_name"] == "Me"
        assert data["role"] == "admin"

    async def test_get_current_user_unauthorized(self, client: AsyncClient):
        """Test /me without token."""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401


class TestProfileUpdate:
    """Tests for profile update endpoint."""

    async def test_update_profile(self, client: AsyncClient, db_session: AsyncSession):
        """Test updating user profile."""
        # Setup: register and login
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Profile Test",
                "tenant_slug": "profile-test",
                "email": "profile@test.com",
                "password": "profilepass123",
                "first_name": "Old",
                "last_name": "Name",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "profile@test.com", "password": "profilepass123"},
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

    async def test_change_password_success(self, client: AsyncClient, db_session: AsyncSession):
        """Test successful password change."""
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Password Test",
                "tenant_slug": "password-test",
                "email": "password@test.com",
                "password": "oldpassword123",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "password@test.com", "password": "oldpassword123"},
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
            data={"username": "password@test.com", "password": "newpassword456"},
        )
        assert new_login.status_code == 200

    async def test_change_password_wrong_current(self, client: AsyncClient, db_session: AsyncSession):
        """Test password change with wrong current password."""
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Wrong Pass Test",
                "tenant_slug": "wrong-pass-test",
                "email": "wrongpass@test.com",
                "password": "correctpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "wrongpass@test.com", "password": "correctpassword"},
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

    async def test_invite_and_accept(self, client: AsyncClient, db_session: AsyncSession):
        """Test full invite flow."""
        # Setup: register admin
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Invite Test",
                "tenant_slug": "invite-test",
                "email": "admin@invite.com",
                "password": "adminpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@invite.com", "password": "adminpassword"},
        )
        token = login_response.json()["access_token"]
        
        # Invite user
        invite_response = await client.post(
            "/api/v1/auth/invite",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "invited@test.com",
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
            data={"username": "invited@test.com", "password": "invitedpassword123"},
        )
        assert invited_login.status_code == 200

    async def test_invite_requires_admin(self, client: AsyncClient, db_session: AsyncSession):
        """Test that non-admins cannot invite users."""
        # Setup: create admin and member
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Role Test",
                "tenant_slug": "role-test",
                "email": "admin@role.com",
                "password": "adminpassword",
            },
        )
        
        admin_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@role.com", "password": "adminpassword"},
        )
        admin_token = admin_login.json()["access_token"]
        
        # Create member via admin
        await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "email": "member@role.com",
                "password": "memberpassword",
                "role": "member",
            },
        )
        
        # Login as member
        member_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "member@role.com", "password": "memberpassword"},
        )
        member_token = member_login.json()["access_token"]
        
        # Try to invite as member (should fail)
        response = await client.post(
            "/api/v1/auth/invite",
            headers={"Authorization": f"Bearer {member_token}"},
            json={"email": "another@test.com"},
        )
        
        assert response.status_code == 403


class TestCreateUser:
    """Tests for direct user creation endpoint."""

    async def test_create_user_as_admin(self, client: AsyncClient, db_session: AsyncSession):
        """Test admin can create users directly."""
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Create Test",
                "tenant_slug": "create-test",
                "email": "admin@create.com",
                "password": "adminpassword",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "admin@create.com", "password": "adminpassword"},
        )
        token = login_response.json()["access_token"]
        
        # Create user
        response = await client.post(
            "/api/v1/auth/users",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "email": "created@test.com",
                "password": "createdpassword123",
                "role": "member",
                "first_name": "Created",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "created@test.com"
        assert data["role"] == "member"
        
        # Verify user can login
        user_login = await client.post(
            "/api/v1/auth/login",
            data={"username": "created@test.com", "password": "createdpassword123"},
        )
        assert user_login.status_code == 200


class TestDeactivateAccount:
    """Tests for account deactivation."""

    async def test_deactivate_account(self, client: AsyncClient, db_session: AsyncSession):
        """Test user can deactivate their own account."""
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Deactivate Test",
                "tenant_slug": "deactivate-test",
                "email": "deactivate@test.com",
                "password": "deactivatepass",
            },
        )
        
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": "deactivate@test.com", "password": "deactivatepass"},
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
            data={"username": "deactivate@test.com", "password": "deactivatepass"},
        )
        assert failed_login.status_code == 400


class TestForgotPassword:
    """Tests for forgot password flow."""

    async def test_forgot_password_request(self, client: AsyncClient, db_session: AsyncSession):
        """Test forgot password request."""
        # Setup
        await client.post(
            "/api/v1/auth/register-tenant",
            json={
                "tenant_name": "Forgot Test",
                "tenant_slug": "forgot-test",
                "email": "forgot@test.com",
                "password": "forgotpassword",
            },
        )
        
        # Request reset
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "forgot@test.com"},
        )
        
        assert response.status_code == 200
        # Should always return success (doesn't reveal if email exists)
        assert "message" in response.json()

    async def test_forgot_password_nonexistent_email(self, client: AsyncClient, db_session: AsyncSession):
        """Test forgot password with non-existent email returns success."""
        response = await client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@test.com"},
        )
        
        # Should return 200 to not reveal email existence
        assert response.status_code == 200
