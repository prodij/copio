"""Tests for Users API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestUsersAPI:
    """Users API tests."""

    @pytest.fixture
    async def auth_context(self, client: AsyncClient) -> dict:
        """Create a test tenant and user, return auth context with headers and role."""
        tenant_slug = f"test-{uuid4().hex[:8]}"
        email = f"admin-{uuid4().hex[:8]}@test.com"
        tenant_data = {
            "tenant_name": f"Test Tenant {uuid4().hex[:8]}",
            "tenant_slug": tenant_slug,
            "email": email,
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "Admin",
        }
        response = await client.post("/api/v1/auth/register-tenant", json=tenant_data)
        assert response.status_code == 200, f"Failed to register tenant: {response.text}"

        # Login
        login_data = {
            "username": email,
            "password": tenant_data["password"],
        }
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200, f"Failed to login: {response.text}"
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get or create a role for invites
        response = await client.get("/api/v1/roles", headers=headers)
        assert response.status_code == 200
        roles = response.json()
        
        # Use first available role or create one
        if roles:
            role_id = roles[0]["id"]
        else:
            response = await client.post(
                "/api/v1/roles",
                json={"name": "Member", "permissions": ["*:view"]},
                headers=headers,
            )
            assert response.status_code == 201
            role_id = response.json()["id"]

        return {
            "headers": headers,
            "email": email,
            "role_id": role_id,
        }

    @pytest.mark.asyncio
    async def test_get_current_user(self, client: AsyncClient, auth_context: dict):
        """Test getting current user returns authenticated user."""
        response = await client.get("/api/v1/users/me", headers=auth_context["headers"])
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == auth_context["email"]
        assert "id" in data
        assert "is_active" in data

    @pytest.mark.asyncio
    async def test_list_users(self, client: AsyncClient, auth_context: dict):
        """Test listing users returns current tenant's users."""
        response = await client.get("/api/v1/users", headers=auth_context["headers"])
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(u["email"] == auth_context["email"] for u in data)

    @pytest.mark.asyncio
    async def test_invite_user(self, client: AsyncClient, auth_context: dict):
        """Test inviting a new user creates an invite record."""
        new_email = f"newuser-{uuid4().hex[:8]}@example.com"
        response = await client.post(
            "/api/v1/users/invite",
            json={"email": new_email, "role_id": auth_context["role_id"]},
            headers=auth_context["headers"],
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["email"] == new_email
        assert data["role_id"] == auth_context["role_id"]
        assert "token" not in data  # Token should not be exposed in response
        assert "expires_at" in data

    @pytest.mark.asyncio
    async def test_invite_duplicate_email(self, client: AsyncClient, auth_context: dict):
        """Test inviting an existing user returns 409 conflict."""
        # Try to invite the admin user that already exists
        response = await client.post(
            "/api/v1/users/invite",
            json={"email": auth_context["email"], "role_id": auth_context["role_id"]},
            headers=auth_context["headers"],
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_invite_user_invalid_role(self, client: AsyncClient, auth_context: dict):
        """Test inviting with invalid role returns 404."""
        fake_role_id = str(uuid4())
        response = await client.post(
            "/api/v1/users/invite",
            json={"email": "test@example.com", "role_id": fake_role_id},
            headers=auth_context["headers"],
        )
        assert response.status_code == 404



# Standalone tests for invite validation/acceptance (these are public endpoints)
@pytest.mark.asyncio
async def test_validate_invite_token(client: AsyncClient, db_session, test_tenant, test_role, test_user):
    """Test validating an invite token returns invite details."""
    from src.db.models.user_invite import UserInvite
    from datetime import datetime, timedelta, timezone
    
    invite = UserInvite(
        tenant_id=test_tenant.id,
        email="newuser@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)
    
    response = await client.get(f"/api/v1/users/invite/{invite.token}")
    assert response.status_code == 200
    assert response.json()["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_validate_invite_token_not_found(client: AsyncClient):
    """Test validating non-existent token returns 404."""
    fake_token = "a" * 64
    response = await client.get(f"/api/v1/users/invite/{fake_token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_accept_invite(client: AsyncClient, db_session, test_tenant, test_role, test_user):
    """Test accepting an invite creates a user account."""
    from src.db.models.user_invite import UserInvite
    from datetime import datetime, timedelta, timezone
    
    invite = UserInvite(
        tenant_id=test_tenant.id,
        email="accepted@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)
    
    response = await client.post(
        f"/api/v1/users/invite/{invite.token}/accept",
        json={"password": "SecurePassword123!", "first_name": "New", "last_name": "User"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "accepted@example.com"


@pytest.mark.asyncio
async def test_accept_expired_invite(client: AsyncClient, db_session, test_tenant, test_role, test_user):
    """Test accepting expired invite returns 410 Gone."""
    from src.db.models.user_invite import UserInvite
    from datetime import datetime, timedelta, timezone
    
    invite = UserInvite(
        tenant_id=test_tenant.id,
        email="expired@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)
    
    response = await client.post(
        f"/api/v1/users/invite/{invite.token}/accept",
        json={"password": "SecurePassword123!"},
    )
    assert response.status_code == 410  # Gone


@pytest.mark.asyncio
async def test_accept_invite_not_found(client: AsyncClient):
    """Test accepting non-existent invite returns 404."""
    fake_token = "b" * 64
    response = await client.post(
        f"/api/v1/users/invite/{fake_token}/accept",
        json={"password": "SecurePassword123!"},
    )
    assert response.status_code == 404
