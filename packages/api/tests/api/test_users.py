"""Tests for Users API endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_users(client: AsyncClient, test_tenant, test_user, db_session):
    """Test listing users returns current tenant's users."""
    response = await client.get("/api/v1/users")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) >= 1
    assert any(u["email"] == test_user.email for u in data)


@pytest.mark.asyncio
async def test_invite_user(client: AsyncClient, test_tenant, test_role, admin_user, db_session):
    """Test inviting a new user creates an invite record."""
    response = await client.post(
        "/api/v1/users/invite",
        json={"email": "newuser@example.com", "role_id": str(test_role.id)},
    )
    assert response.status_code == 201
    
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["role_id"] == str(test_role.id)
    assert "token" not in data  # Token should not be exposed in response


@pytest.mark.asyncio
async def test_invite_duplicate_email(client: AsyncClient, test_tenant, test_role, test_user, admin_user, db_session):
    """Test inviting an existing user returns 409 conflict."""
    # Try to invite existing user
    response = await client.post(
        "/api/v1/users/invite",
        json={"email": test_user.email, "role_id": str(test_role.id)},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_get_current_user(client: AsyncClient, test_user):
    """Test getting current user returns authenticated user."""
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 200
    assert response.json()["email"] == test_user.email
