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
async def test_validate_invite_token(client_with_db):
    """Test validating an invite token returns invite details."""
    from src.db.models.user_invite import UserInvite
    from src.db.models.tenant import Tenant
    from src.db.models.role import Role
    from src.db.models.user import User
    from datetime import datetime, timedelta, timezone
    
    client, session = client_with_db
    
    # Create test data
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    role = Role(id=uuid4(), tenant_id=tenant.id, name="Test Role", permissions=["*:view"])
    session.add(role)
    await session.flush()
    
    user = User(
        id=uuid4(), email=f"inviter-{uuid4().hex[:8]}@example.com",
        hashed_password="placeholder", tenant_id=tenant.id, is_active=True
    )
    session.add(user)
    await session.flush()
    
    invite = UserInvite(
        tenant_id=tenant.id,
        email="newuser@example.com",
        role_id=role.id,
        invited_by=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    
    response = await client.get(f"/api/v1/users/invite/{invite.token}")
    assert response.status_code == 200
    assert response.json()["email"] == "newuser@example.com"


@pytest.mark.asyncio
async def test_validate_invite_token_not_found(client_with_db):
    """Test validating non-existent token returns 404."""
    client, _ = client_with_db
    fake_token = "a" * 64
    response = await client.get(f"/api/v1/users/invite/{fake_token}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_accept_invite(client_with_db):
    """Test accepting an invite creates a user account."""
    from src.db.models.user_invite import UserInvite
    from src.db.models.tenant import Tenant
    from src.db.models.role import Role
    from src.db.models.user import User
    from datetime import datetime, timedelta, timezone
    
    client, session = client_with_db
    
    # Create test data
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    role = Role(id=uuid4(), tenant_id=tenant.id, name="Test Role", permissions=["*:view"])
    session.add(role)
    await session.flush()
    
    user = User(
        id=uuid4(), email=f"inviter-{uuid4().hex[:8]}@example.com",
        hashed_password="placeholder", tenant_id=tenant.id, is_active=True
    )
    session.add(user)
    await session.flush()
    
    invite = UserInvite(
        tenant_id=tenant.id,
        email="accepted@example.com",
        role_id=role.id,
        invited_by=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    
    response = await client.post(
        f"/api/v1/users/invite/{invite.token}/accept",
        json={"password": "SecurePassword123!", "first_name": "New", "last_name": "User"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "accepted@example.com"


@pytest.mark.asyncio
async def test_accept_expired_invite(client_with_db):
    """Test accepting expired invite returns 410 Gone."""
    from src.db.models.user_invite import UserInvite
    from src.db.models.tenant import Tenant
    from src.db.models.role import Role
    from src.db.models.user import User
    from datetime import datetime, timedelta, timezone
    
    client, session = client_with_db
    
    # Create test data
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    role = Role(id=uuid4(), tenant_id=tenant.id, name="Test Role", permissions=["*:view"])
    session.add(role)
    await session.flush()
    
    user = User(
        id=uuid4(), email=f"inviter-{uuid4().hex[:8]}@example.com",
        hashed_password="placeholder", tenant_id=tenant.id, is_active=True
    )
    session.add(user)
    await session.flush()
    
    invite = UserInvite(
        tenant_id=tenant.id,
        email="expired@example.com",
        role_id=role.id,
        invited_by=user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),  # Already expired
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    
    response = await client.post(
        f"/api/v1/users/invite/{invite.token}/accept",
        json={"password": "SecurePassword123!"},
    )
    assert response.status_code == 410  # Gone


@pytest.mark.asyncio
async def test_accept_invite_not_found(client_with_db):
    """Test accepting non-existent invite returns 404."""
    client, _ = client_with_db
    fake_token = "b" * 64
    response = await client.post(
        f"/api/v1/users/invite/{fake_token}/accept",
        json={"password": "SecurePassword123!"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_user(client: AsyncClient, test_tenant, test_user, admin_user, db_session):
    """Test updating a user's details."""
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"first_name": "Updated", "last_name": "Name"},
    )
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"


@pytest.mark.asyncio
async def test_deactivate_user(client: AsyncClient, test_tenant, test_user, admin_user, db_session):
    """Test deactivating a user (soft delete)."""
    response = await client.delete(f"/api/v1/users/{test_user.id}")
    assert response.status_code == 204
    
    # Verify user is deactivated
    from sqlalchemy import select
    from src.db.models.user import User
    result = await db_session.execute(select(User).where(User.id == test_user.id))
    user = result.scalar_one()
    assert user.is_active is False


@pytest.mark.asyncio
async def test_change_user_role(client: AsyncClient, test_tenant, test_user, test_role, admin_user, db_session):
    """Test changing a user's role."""
    from src.db.models.role import Role
    
    new_role = Role(tenant_id=test_tenant.id, name="New Role", permissions=["products:view"])
    db_session.add(new_role)
    await db_session.commit()
    
    response = await client.patch(
        f"/api/v1/users/{test_user.id}",
        json={"role_id": str(new_role.id)},
    )
    assert response.status_code == 200
