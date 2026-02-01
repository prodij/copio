"""Tests for Roles API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestRolesAPI:
    """Roles API tests."""

    @pytest.fixture
    async def auth_context(self, client: AsyncClient) -> dict:
        """Create a test tenant and user, return auth headers and tenant info."""
        # Register a test tenant
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
        tenant_id = response.json()["tenant_id"]

        # Login
        login_data = {
            "username": tenant_data["email"],
            "password": tenant_data["password"],
        }
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        
        return {
            "headers": {"Authorization": f"Bearer {token}"},
            "tenant_id": tenant_id,
        }

    async def _create_role(
        self,
        client: AsyncClient,
        headers: dict,
        name: str = "Test Role",
        permissions: list | None = None,
    ) -> dict:
        """Helper to create a role via API."""
        if permissions is None:
            permissions = ["products:view"]
        response = await client.post(
            "/api/v1/roles/",
            json={"name": name, "permissions": permissions},
            headers=headers,
        )
        assert response.status_code == 201
        return response.json()

    # ==========================================================================
    # CREATE TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_create_role(self, client: AsyncClient, auth_context: dict):
        """Test creating a role."""
        response = await client.post(
            "/api/v1/roles/",
            json={"name": "Test Role", "permissions": ["products:view", "products:edit"]},
            headers=auth_context["headers"],
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Role"
        assert "products:view" in data["permissions"]
        assert "products:edit" in data["permissions"]
        assert "id" in data
        assert data["is_system"] is False

    @pytest.mark.asyncio
    async def test_create_role_duplicate_name(self, client: AsyncClient, auth_context: dict):
        """Test that duplicate role names within a tenant are rejected."""
        role_name = f"Manager {uuid4().hex[:8]}"
        
        # Create first role
        await self._create_role(client, auth_context["headers"], role_name)
        
        # Try to create duplicate
        response = await client.post(
            "/api/v1/roles/",
            json={"name": role_name, "permissions": ["products:view"]},
            headers=auth_context["headers"],
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_create_role_with_invalid_permissions(self, client: AsyncClient, auth_context: dict):
        """Test that invalid permissions are rejected."""
        response = await client.post(
            "/api/v1/roles/",
            json={
                "name": f"Bad Role {uuid4().hex[:8]}",
                "permissions": ["invalid:permission", "fake:action"],
            },
            headers=auth_context["headers"],
        )
        # Should fail validation
        assert response.status_code == 422

    # ==========================================================================
    # LIST TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_list_roles(self, client: AsyncClient, auth_context: dict):
        """Test listing roles."""
        # Create a role
        await self._create_role(client, auth_context["headers"], "List Test Role")

        # List roles
        response = await client.get("/api/v1/roles/", headers=auth_context["headers"])
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert len(data["data"]) >= 1

    # ==========================================================================
    # GET TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_get_role(self, client: AsyncClient, auth_context: dict):
        """Test getting a single role."""
        # Create a role
        role = await self._create_role(client, auth_context["headers"], "Get Test Role")
        role_id = role["id"]

        # Get the role
        response = await client.get(
            f"/api/v1/roles/{role_id}",
            headers=auth_context["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Get Test Role"

    @pytest.mark.asyncio
    async def test_get_role_not_found(self, client: AsyncClient, auth_context: dict):
        """Test getting a non-existent role returns 404."""
        fake_id = uuid4()
        response = await client.get(
            f"/api/v1/roles/{fake_id}",
            headers=auth_context["headers"],
        )
        assert response.status_code == 404

    # ==========================================================================
    # UPDATE TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_update_role(self, client: AsyncClient, auth_context: dict):
        """Test updating a role."""
        # Create a role
        role = await self._create_role(
            client,
            auth_context["headers"],
            "Custom",
            permissions=["products:view"],
        )
        role_id = role["id"]

        # Update the role
        response = await client.patch(
            f"/api/v1/roles/{role_id}",
            json={"name": "Updated Role", "permissions": ["products:view", "products:edit"]},
            headers=auth_context["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Role"
        assert "products:edit" in data["permissions"]

    @pytest.mark.asyncio
    async def test_update_role_partial(self, client: AsyncClient, auth_context: dict):
        """Test partial update of a role (only name)."""
        role = await self._create_role(
            client,
            auth_context["headers"],
            "Original Name",
            permissions=["products:view"],
        )
        role_id = role["id"]

        # Update only the name
        response = await client.patch(
            f"/api/v1/roles/{role_id}",
            json={"name": "New Name"},
            headers=auth_context["headers"],
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Name"
        assert data["permissions"] == ["products:view"]

    @pytest.mark.asyncio
    async def test_update_role_not_found(self, client: AsyncClient, auth_context: dict):
        """Test updating a non-existent role returns 404."""
        fake_id = uuid4()
        response = await client.patch(
            f"/api/v1/roles/{fake_id}",
            json={"name": "Updated"},
            headers=auth_context["headers"],
        )
        assert response.status_code == 404

    # ==========================================================================
    # DELETE TESTS
    # ==========================================================================

    @pytest.mark.asyncio
    async def test_delete_role(self, client: AsyncClient, auth_context: dict):
        """Test deleting a role."""
        # Create a role
        role = await self._create_role(client, auth_context["headers"], "ToDelete")
        role_id = role["id"]

        # Delete the role
        response = await client.delete(
            f"/api/v1/roles/{role_id}",
            headers=auth_context["headers"],
        )
        assert response.status_code == 204

        # Verify it's gone
        response = await client.get(
            f"/api/v1/roles/{role_id}",
            headers=auth_context["headers"],
        )
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_role_not_found(self, client: AsyncClient, auth_context: dict):
        """Test deleting a non-existent role returns 404."""
        fake_id = uuid4()
        response = await client.delete(
            f"/api/v1/roles/{fake_id}",
            headers=auth_context["headers"],
        )
        assert response.status_code == 404
