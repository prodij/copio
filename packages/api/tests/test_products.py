"""Tests for products API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestProductsAPI:
    """Product API tests."""

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient) -> dict:
        """Create a test tenant and user, return auth headers."""
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

        # Login
        login_data = {
            "username": tenant_data["email"],
            "password": tenant_data["password"],
        }
        response = await client.post(
            "/api/v1/auth/login",
            data=login_data,
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    @pytest.mark.asyncio
    async def test_create_product(self, client: AsyncClient, auth_headers: dict):
        """Test creating a product."""
        product_data = {
            "sku": f"TEST-{uuid4().hex[:8]}",
            "name": "Test Product",
            "productType": "SIMPLE",
            "status": "DRAFT",
            "brand": "Test Brand",
            "costPrice": "19.99",
            "msrp": "29.99",
        }
        response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["sku"] == product_data["sku"]
        assert data["name"] == product_data["name"]
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_products(self, client: AsyncClient, auth_headers: dict):
        """Test listing products."""
        # Create a product first
        product_data = {
            "sku": f"LIST-{uuid4().hex[:8]}",
            "name": "List Test Product",
        }
        await client.post("/api/v1/products/", json=product_data, headers=auth_headers)

        # List products
        response = await client.get("/api/v1/products/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1

    @pytest.mark.asyncio
    async def test_get_product(self, client: AsyncClient, auth_headers: dict):
        """Test getting a single product."""
        # Create a product
        product_data = {
            "sku": f"GET-{uuid4().hex[:8]}",
            "name": "Get Test Product",
        }
        create_response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # Get the product
        response = await client.get(
            f"/api/v1/products/{product_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == product_id
        assert data["sku"] == product_data["sku"]

    @pytest.mark.asyncio
    async def test_update_product(self, client: AsyncClient, auth_headers: dict):
        """Test updating a product."""
        # Create a product
        product_data = {
            "sku": f"UPDATE-{uuid4().hex[:8]}",
            "name": "Original Name",
        }
        create_response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # Update the product
        update_data = {"name": "Updated Name", "brand": "New Brand"}
        response = await client.patch(
            f"/api/v1/products/{product_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["brand"] == "New Brand"

    @pytest.mark.asyncio
    async def test_delete_product(self, client: AsyncClient, auth_headers: dict):
        """Test deleting a product."""
        # Create a product
        product_data = {
            "sku": f"DELETE-{uuid4().hex[:8]}",
            "name": "Delete Test Product",
        }
        create_response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # Delete the product
        response = await client.delete(
            f"/api/v1/products/{product_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

        # Verify it's deleted
        get_response = await client.get(
            f"/api/v1/products/{product_id}",
            headers=auth_headers,
        )
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_sku_rejected(self, client: AsyncClient, auth_headers: dict):
        """Test that duplicate SKUs are rejected."""
        sku = f"DUPE-{uuid4().hex[:8]}"
        product_data = {
            "sku": sku,
            "name": "First Product",
        }
        # First create should succeed
        response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Second create with same SKU should fail
        product_data["name"] = "Second Product"
        response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_product_image_operations(self, client: AsyncClient, auth_headers: dict):
        """Test product image CRUD."""
        # Create a product
        product_data = {
            "sku": f"IMG-{uuid4().hex[:8]}",
            "name": "Image Test Product",
        }
        create_response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # Add an image
        image_data = {
            "url": "https://example.com/image.jpg",
            "altText": "Test image",
            "position": 0,
        }
        response = await client.post(
            f"/api/v1/products/{product_id}/images",
            json=image_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        image_id = response.json()["id"]

        # Delete the image
        response = await client.delete(
            f"/api/v1/products/{product_id}/images/{image_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_product_attribute_operations(self, client: AsyncClient, auth_headers: dict):
        """Test product attribute CRUD."""
        # Create a product
        product_data = {
            "sku": f"ATTR-{uuid4().hex[:8]}",
            "name": "Attribute Test Product",
        }
        create_response = await client.post(
            "/api/v1/products/",
            json=product_data,
            headers=auth_headers,
        )
        product_id = create_response.json()["id"]

        # Add an attribute
        attr_data = {
            "name": "Color",
            "value": "Blue",
            "group": "Physical",
        }
        response = await client.post(
            f"/api/v1/products/{product_id}/attributes",
            json=attr_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        attr_id = response.json()["id"]

        # Update the attribute
        update_data = {"name": "Color", "value": "Red"}
        response = await client.patch(
            f"/api/v1/products/{product_id}/attributes/{attr_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["value"] == "Red"

        # Delete the attribute
        response = await client.delete(
            f"/api/v1/products/{product_id}/attributes/{attr_id}",
            headers=auth_headers,
        )
        assert response.status_code == 204
