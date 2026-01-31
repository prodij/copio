"""Tests for vendors API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestVendorsAPI:
    """Vendor API tests."""

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

        login_data = {
            "username": tenant_data["email"],
            "password": tenant_data["password"],
        }
        response = await client.post("/api/v1/auth/login", data=login_data)
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_create_vendor(self, client: AsyncClient, auth_headers: dict):
        """Test creating a vendor."""
        vendor_data = {
            "name": "Test Vendor",
            "code": f"VND-{uuid4().hex[:8]}",
            "tier": "STANDARD",
            "leadTimeDays": 14,
            "currency": "USD",
        }
        response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == vendor_data["name"]
        assert data["code"] == vendor_data["code"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_vendors(self, client: AsyncClient, auth_headers: dict):
        """Test listing vendors."""
        # Create a vendor first
        vendor_data = {
            "name": "List Test Vendor",
            "code": f"LIST-{uuid4().hex[:8]}",
        }
        await client.post("/api/v1/vendors/", json=vendor_data, headers=auth_headers)

        # List vendors
        response = await client.get("/api/v1/vendors/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_get_vendor(self, client: AsyncClient, auth_headers: dict):
        """Test getting a single vendor."""
        vendor_data = {
            "name": "Get Test Vendor",
            "code": f"GET-{uuid4().hex[:8]}",
        }
        create_response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        vendor_id = create_response.json()["id"]

        response = await client.get(
            f"/api/v1/vendors/{vendor_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == vendor_id
        assert data["name"] == vendor_data["name"]

    @pytest.mark.asyncio
    async def test_update_vendor(self, client: AsyncClient, auth_headers: dict):
        """Test updating a vendor."""
        vendor_data = {
            "name": "Original Vendor Name",
            "code": f"UPD-{uuid4().hex[:8]}",
        }
        create_response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        vendor_id = create_response.json()["id"]

        update_data = {
            "name": "Updated Vendor Name",
            "tier": "PREFERRED",
            "leadTimeDays": 7,
        }
        response = await client.patch(
            f"/api/v1/vendors/{vendor_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Vendor Name"
        assert data["tier"] == "PREFERRED"

    @pytest.mark.asyncio
    async def test_delete_vendor(self, client: AsyncClient, auth_headers: dict):
        """Test deleting a vendor."""
        vendor_data = {
            "name": "Delete Test Vendor",
            "code": f"DEL-{uuid4().hex[:8]}",
        }
        create_response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        vendor_id = create_response.json()["id"]

        response = await client.delete(
            f"/api/v1/vendors/{vendor_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            f"/api/v1/vendors/{vendor_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_vendor_stats(self, client: AsyncClient, auth_headers: dict):
        """Test vendor stats summary."""
        # Create some vendors
        for tier in ["STANDARD", "PREFERRED", "STRATEGIC"]:
            vendor_data = {
                "name": f"Stats Test Vendor {tier}",
                "code": f"STAT-{uuid4().hex[:8]}",
                "tier": tier,
            }
            await client.post("/api/v1/vendors/", json=vendor_data, headers=auth_headers)

        response = await client.get(
            "/api/v1/vendors/stats/summary",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "byTier" in data
        assert "contractsExpiringSoon" in data

    @pytest.mark.asyncio
    async def test_vendor_contact_operations(self, client: AsyncClient, auth_headers: dict):
        """Test vendor contact CRUD."""
        # Create a vendor
        vendor_data = {
            "name": "Contact Test Vendor",
            "code": f"CONT-{uuid4().hex[:8]}",
        }
        create_response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        vendor_id = create_response.json()["id"]

        # Add a contact
        contact_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "555-1234",
            "role": "SALES",
            "isPrimary": True,
        }
        response = await client.post(
            f"/api/v1/vendors/{vendor_id}/contacts",
            json=contact_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        contact_id = response.json()["id"]

        # List contacts
        response = await client.get(
            f"/api/v1/vendors/{vendor_id}/contacts",
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert len(response.json()) >= 1

    @pytest.mark.asyncio
    async def test_duplicate_vendor_code_rejected(self, client: AsyncClient, auth_headers: dict):
        """Test that duplicate vendor codes are rejected."""
        code = f"DUPE-{uuid4().hex[:8]}"
        vendor_data = {
            "name": "First Vendor",
            "code": code,
        }
        # First create should succeed
        response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Second create with same code should fail
        vendor_data["name"] = "Second Vendor"
        response = await client.post(
            "/api/v1/vendors/",
            json=vendor_data,
            headers=auth_headers,
        )
        assert response.status_code == 409
