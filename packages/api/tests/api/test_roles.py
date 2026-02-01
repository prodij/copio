"""Tests for Roles API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestRolesAPI:
    """Roles API tests."""

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
    async def test_list_roles(self, client: AsyncClient, auth_headers: dict):
        """Test listing roles for a tenant."""
        response = await client.get("/api/v1/roles/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        # Response is paginated with {data: [...], total: N}
        assert "data" in data
        assert "total" in data
        assert isinstance(data["data"], list)

    @pytest.mark.asyncio
    async def test_create_role(self, client: AsyncClient, auth_headers: dict):
        """Test creating a new role."""
        role_name = f"Warehouse Staff {uuid4().hex[:8]}"
        response = await client.post(
            "/api/v1/roles/",
            json={
                "name": role_name,
                "description": "Inventory and receiving",
                "permissions": ["inventory:view", "inventory:adjust", "purchase_orders:view", "purchase_orders:receive"],
            },
            headers=auth_headers,
        )
        assert response.status_code == 201
        
        data = response.json()
        assert data["name"] == role_name
        assert data["is_system"] is False
        assert "inventory:view" in data["permissions"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_role_duplicate_name(self, client: AsyncClient, auth_headers: dict):
        """Test that duplicate role names within a tenant are rejected."""
        role_name = f"Manager {uuid4().hex[:8]}"
        
        # Create first role
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["*:view"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        
        # Try to create duplicate
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view"]},
            headers=auth_headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_list_roles_after_create(self, client: AsyncClient, auth_headers: dict):
        """Test that created roles appear in list."""
        role_name = f"Test Role {uuid4().hex[:8]}"
        
        # Create a role
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view", "products:create"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        
        # List roles and verify it's there
        response = await client.get("/api/v1/roles/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert any(r["name"] == role_name for r in data["data"])

    @pytest.mark.asyncio
    async def test_create_role_with_invalid_permissions(self, client: AsyncClient, auth_headers: dict):
        """Test that invalid permissions are rejected."""
        response = await client.post(
            "/api/v1/roles/",
            json={
                "name": f"Bad Role {uuid4().hex[:8]}",
                "permissions": ["invalid:permission", "fake:action"],
            },
            headers=auth_headers,
        )
        # Should fail validation
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_get_role(self, client: AsyncClient, auth_headers: dict):
        """Test getting a single role by ID."""
        role_name = f"Get Test Role {uuid4().hex[:8]}"
        
        # Create role
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        role_id = response.json()["id"]
        
        # Get role
        response = await client.get(f"/api/v1/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["name"] == role_name

    @pytest.mark.asyncio
    async def test_update_role(self, client: AsyncClient, auth_headers: dict):
        """Test updating a role."""
        role_name = f"Update Test Role {uuid4().hex[:8]}"
        
        # Create role
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        role_id = response.json()["id"]
        
        # Update role
        new_name = f"Updated Role {uuid4().hex[:8]}"
        response = await client.patch(
            f"/api/v1/roles/{role_id}",
            json={"name": new_name, "permissions": ["products:view", "products:edit"]},
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == new_name
        assert "products:edit" in response.json()["permissions"]

    @pytest.mark.asyncio
    async def test_delete_role(self, client: AsyncClient, auth_headers: dict):
        """Test deleting a role."""
        role_name = f"Delete Test Role {uuid4().hex[:8]}"
        
        # Create role
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view"]},
            headers=auth_headers,
        )
        assert response.status_code == 201
        role_id = response.json()["id"]
        
        # Delete role
        response = await client.delete(f"/api/v1/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 204
        
        # Verify it's gone
        response = await client.get(f"/api/v1/roles/{role_id}", headers=auth_headers)
        assert response.status_code == 404
