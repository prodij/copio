"""Tests for tenant isolation - ensuring data is properly scoped."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestTenantIsolation:
    """Test that tenants cannot access each other's data."""

    async def create_tenant_with_auth(self, client: AsyncClient, suffix: str) -> dict:
        """Create a tenant and return auth headers."""
        tenant_data = {
            "tenant_name": f"Tenant {suffix}",
            "tenant_slug": f"tenant-{suffix}",
            "email": f"admin-{suffix}@test.com",
            "password": "testpassword123",
        }
        response = await client.post("/api/v1/auth/register-tenant", json=tenant_data)
        assert response.status_code == 200

        login_data = {
            "username": tenant_data["email"],
            "password": tenant_data["password"],
        }
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_products_isolated_between_tenants(self, client: AsyncClient):
        """Test that products are isolated between tenants."""
        # Create two tenants
        suffix1 = uuid4().hex[:8]
        suffix2 = uuid4().hex[:8]
        auth1 = await self.create_tenant_with_auth(client, suffix1)
        auth2 = await self.create_tenant_with_auth(client, suffix2)

        # Tenant 1 creates a product
        product_data = {
            "sku": f"ISO-{uuid4().hex[:8]}",
            "name": "Tenant 1 Product",
        }
        response = await client.post("/api/v1/products/", json=product_data, headers=auth1)
        assert response.status_code == 201
        product_id = response.json()["id"]

        # Tenant 1 can see the product
        response = await client.get(f"/api/v1/products/{product_id}", headers=auth1)
        assert response.status_code == 200

        # Tenant 2 cannot see the product
        response = await client.get(f"/api/v1/products/{product_id}", headers=auth2)
        assert response.status_code == 404

        # Tenant 2's product list is empty (or doesn't include tenant 1's product)
        response = await client.get("/api/v1/products/", headers=auth2)
        assert response.status_code == 200
        products = response.json()["data"]
        product_ids = [p["id"] for p in products]
        assert product_id not in product_ids

    @pytest.mark.asyncio
    async def test_vendors_isolated_between_tenants(self, client: AsyncClient):
        """Test that vendors are isolated between tenants."""
        suffix1 = uuid4().hex[:8]
        suffix2 = uuid4().hex[:8]
        auth1 = await self.create_tenant_with_auth(client, suffix1)
        auth2 = await self.create_tenant_with_auth(client, suffix2)

        # Tenant 1 creates a vendor
        vendor_data = {
            "name": "Tenant 1 Vendor",
            "code": f"VND-{uuid4().hex[:8]}",
        }
        response = await client.post("/api/v1/vendors/", json=vendor_data, headers=auth1)
        assert response.status_code == 201
        vendor_id = response.json()["id"]

        # Tenant 1 can see the vendor
        response = await client.get(f"/api/v1/vendors/{vendor_id}", headers=auth1)
        assert response.status_code == 200

        # Tenant 2 cannot see the vendor
        response = await client.get(f"/api/v1/vendors/{vendor_id}", headers=auth2)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_locations_isolated_between_tenants(self, client: AsyncClient):
        """Test that locations are isolated between tenants."""
        suffix1 = uuid4().hex[:8]
        suffix2 = uuid4().hex[:8]
        auth1 = await self.create_tenant_with_auth(client, suffix1)
        auth2 = await self.create_tenant_with_auth(client, suffix2)

        # Tenant 1 creates a location
        location_data = {
            "name": "Tenant 1 Warehouse",
            "type": "WAREHOUSE",
        }
        response = await client.post("/api/v1/locations/", json=location_data, headers=auth1)
        assert response.status_code == 201
        location_id = response.json()["id"]

        # Tenant 2 cannot access it
        response = await client.get(f"/api/v1/locations/{location_id}", headers=auth2)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_cannot_update_other_tenant_data(self, client: AsyncClient):
        """Test that one tenant cannot update another tenant's data."""
        suffix1 = uuid4().hex[:8]
        suffix2 = uuid4().hex[:8]
        auth1 = await self.create_tenant_with_auth(client, suffix1)
        auth2 = await self.create_tenant_with_auth(client, suffix2)

        # Tenant 1 creates a product
        product_data = {
            "sku": f"UPD-{uuid4().hex[:8]}",
            "name": "Original Name",
        }
        response = await client.post("/api/v1/products/", json=product_data, headers=auth1)
        assert response.status_code == 201
        product_id = response.json()["id"]

        # Tenant 2 tries to update it
        update_data = {"name": "Hacked Name"}
        response = await client.patch(
            f"/api/v1/products/{product_id}",
            json=update_data,
            headers=auth2,
        )
        assert response.status_code == 404

        # Verify original name unchanged
        response = await client.get(f"/api/v1/products/{product_id}", headers=auth1)
        assert response.json()["name"] == "Original Name"

    @pytest.mark.asyncio
    async def test_cannot_delete_other_tenant_data(self, client: AsyncClient):
        """Test that one tenant cannot delete another tenant's data."""
        suffix1 = uuid4().hex[:8]
        suffix2 = uuid4().hex[:8]
        auth1 = await self.create_tenant_with_auth(client, suffix1)
        auth2 = await self.create_tenant_with_auth(client, suffix2)

        # Tenant 1 creates a vendor
        vendor_data = {
            "name": "Protected Vendor",
            "code": f"PROT-{uuid4().hex[:8]}",
        }
        response = await client.post("/api/v1/vendors/", json=vendor_data, headers=auth1)
        assert response.status_code == 201
        vendor_id = response.json()["id"]

        # Tenant 2 tries to delete it
        response = await client.delete(f"/api/v1/vendors/{vendor_id}", headers=auth2)
        assert response.status_code == 404

        # Verify still exists for tenant 1
        response = await client.get(f"/api/v1/vendors/{vendor_id}", headers=auth1)
        assert response.status_code == 200
