# packages/api/tests/api/test_permissions.py
"""Tests for Permissions API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestPermissionsAPI:
    """Permissions API tests."""

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient) -> dict:
        """Create a test tenant and user, return auth headers."""
        tenant_data = {
            "tenant_name": f"Test Tenant {uuid4().hex[:8]}",
            "tenant_slug": f"test-{uuid4().hex[:8]}",
            "email": f"admin-{uuid4().hex[:8]}@test.com",
            "password": "testpassword123",
            "first_name": "Test",
            "last_name": "Admin",
        }
        response = await client.post("/api/v1/auth/register-tenant", json=tenant_data)
        assert response.status_code == 200

        # Login
        login_data = {
            "username": tenant_data["email"],
            "password": tenant_data["password"],
        }
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_list_all_permissions(self, client: AsyncClient, auth_headers: dict):
        """Test listing all available permissions."""
        response = await client.get("/api/v1/permissions", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "products:view" in data
        assert "inventory:adjust" in data
        assert "purchase_orders:receive" in data

    @pytest.mark.asyncio
    async def test_list_permissions_by_resource(self, client: AsyncClient, auth_headers: dict):
        """Test listing permissions grouped by resource."""
        response = await client.get("/api/v1/permissions/by-resource", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "products" in data
        assert "view" in data["products"]
        assert "create" in data["products"]
        assert "inventory" in data
        assert "adjust" in data["inventory"]

    @pytest.mark.asyncio
    async def test_get_my_permissions_admin(self, client: AsyncClient, auth_headers: dict):
        """Test getting permissions for admin user with all permissions."""
        # First, create an admin role with all permissions
        response = await client.post(
            "/api/v1/roles",
            json={
                "name": f"Admin {uuid4().hex[:8]}",
                "permissions": ["*:*"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        role_id = response.json()["id"]
        
        # Assign role to current user
        response = await client.get("/api/v1/users/me", headers=auth_headers)
        assert response.status_code == 200
        user_id = response.json()["id"]
        
        response = await client.post(
            f"/api/v1/users/{user_id}/roles/{role_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # Get my permissions
        response = await client.get("/api/v1/permissions/me", headers=auth_headers)
        assert response.status_code == 200
        
        data = response.json()
        # Admin should have all permissions
        assert "products:view" in data
        assert "products:delete" in data
        assert "users:invite" in data

    @pytest.mark.asyncio
    async def test_get_my_permissions_limited(self, client: AsyncClient, auth_headers: dict):
        """Test getting permissions for user with limited permissions."""
        # Create a viewer role with only view permissions
        response = await client.post(
            "/api/v1/roles",
            json={
                "name": f"Viewer {uuid4().hex[:8]}",
                "permissions": ["*:view"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        viewer_role_id = response.json()["id"]
        
        # Create a new user with only the viewer role (not admin)
        new_user_email = f"viewer-{uuid4().hex[:8]}@test.com"
        response = await client.post(
            "/api/v1/auth/users",
            json={
                "email": new_user_email,
                "password": "viewerpassword123",
                "role": "member",
            },
            headers=auth_headers,
        )
        assert response.status_code == 200
        new_user_id = response.json()["id"]
        
        # Assign only viewer role to the new user
        response = await client.post(
            f"/api/v1/users/{new_user_id}/roles/{viewer_role_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        
        # Login as the new viewer user
        login_response = await client.post(
            "/api/v1/auth/login",
            data={"username": new_user_email, "password": "viewerpassword123"},
        )
        assert login_response.status_code == 200
        viewer_token = login_response.json()["access_token"]
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}
        
        # Get permissions for the viewer user
        response = await client.get("/api/v1/permissions/me", headers=viewer_headers)
        assert response.status_code == 200
        
        data = response.json()
        assert "products:view" in data
        assert "products:create" not in data
