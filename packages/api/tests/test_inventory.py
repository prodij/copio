"""Tests for inventory API endpoints (locations, stock items, stock movements)."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


class TestInventoryAPI:
    """Inventory API tests."""

    @pytest.fixture
    async def auth_headers(self, client: AsyncClient) -> dict:
        """Create a test tenant and user, return auth headers."""
        tenant_data = {
            "tenant_name": f"Test Tenant {uuid4().hex[:8]}",
            "tenant_slug": f"test-{uuid4().hex[:8]}",
            "email": f"admin-{uuid4().hex[:8]}@test.com",
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

    # =============================================================================
    # LOCATIONS
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_location(self, client: AsyncClient, auth_headers: dict):
        """Test creating a location."""
        location_data = {
            "name": "Main Warehouse",
            "type": "WAREHOUSE",
            "isActive": True,
            "address": {"city": "Los Angeles", "state": "CA"},
        }
        response = await client.post(
            "/api/v1/locations/",
            json=location_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == location_data["name"]
        assert data["type"] == location_data["type"]

    @pytest.mark.asyncio
    async def test_list_locations(self, client: AsyncClient, auth_headers: dict):
        """Test listing locations."""
        # Create a location
        location_data = {"name": "Test Location", "type": "WAREHOUSE"}
        await client.post("/api/v1/locations/", json=location_data, headers=auth_headers)

        response = await client.get("/api/v1/locations/", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_update_location(self, client: AsyncClient, auth_headers: dict):
        """Test updating a location."""
        location_data = {"name": "Original Name", "type": "WAREHOUSE"}
        create_response = await client.post(
            "/api/v1/locations/",
            json=location_data,
            headers=auth_headers,
        )
        location_id = create_response.json()["id"]

        update_data = {"name": "Updated Name", "isActive": False}
        response = await client.patch(
            f"/api/v1/locations/{location_id}",
            json=update_data,
            headers=auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    # =============================================================================
    # STOCK ITEMS
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_stock_item(self, client: AsyncClient, auth_headers: dict):
        """Test creating a stock item."""
        # Create a product
        product_data = {"sku": f"STOCK-{uuid4().hex[:8]}", "name": "Stock Test Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        # Create a location
        location_data = {"name": "Stock Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        # Create stock item
        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 100,
            "reorderPoint": 10,
        }
        response = await client.post(
            "/api/v1/stock-items/",
            json=stock_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["quantityAvailable"] == 100

    @pytest.mark.asyncio
    async def test_list_stock_items_by_location(self, client: AsyncClient, auth_headers: dict):
        """Test listing stock items by location."""
        # Create product and location
        product_data = {"sku": f"LOC-{uuid4().hex[:8]}", "name": "Location Test Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        location_data = {"name": "Filter Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        # Create stock item
        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 50,
        }
        await client.post("/api/v1/stock-items/", json=stock_data, headers=auth_headers)

        # List by location
        response = await client.get(
            f"/api/v1/stock-items/by-location/{location_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1

    @pytest.mark.asyncio
    async def test_duplicate_stock_item_rejected(self, client: AsyncClient, auth_headers: dict):
        """Test that duplicate stock items (same product+location) are rejected."""
        product_data = {"sku": f"DUP-{uuid4().hex[:8]}", "name": "Dup Test Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        location_data = {"name": "Dup Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 10,
        }
        # First should succeed
        response = await client.post(
            "/api/v1/stock-items/", json=stock_data, headers=auth_headers
        )
        assert response.status_code == 201

        # Second should fail
        response = await client.post(
            "/api/v1/stock-items/", json=stock_data, headers=auth_headers
        )
        assert response.status_code == 409

    # =============================================================================
    # STOCK MOVEMENTS
    # =============================================================================

    @pytest.mark.asyncio
    async def test_create_stock_movement(self, client: AsyncClient, auth_headers: dict):
        """Test creating a stock movement."""
        # Create product, location, and stock item
        product_data = {"sku": f"MOV-{uuid4().hex[:8]}", "name": "Movement Test Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        location_data = {"name": "Movement Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 100,
        }
        stock_response = await client.post(
            "/api/v1/stock-items/", json=stock_data, headers=auth_headers
        )
        stock_item_id = stock_response.json()["id"]

        # Create a RECEIVE movement
        movement_data = {
            "stockItemId": stock_item_id,
            "type": "RECEIVE",
            "quantity": 50,
            "reference": "PO-001",
            "notes": "Test receipt",
        }
        response = await client.post(
            "/api/v1/stock-movements/",
            json=movement_data,
            headers=auth_headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["type"] == "RECEIVE"
        assert data["quantity"] == 50

        # Verify stock was updated
        stock_response = await client.get(
            f"/api/v1/stock-items/{stock_item_id}",
            headers=auth_headers,
        )
        assert stock_response.json()["quantityAvailable"] == 150  # 100 + 50

    @pytest.mark.asyncio
    async def test_ship_movement_reduces_stock(self, client: AsyncClient, auth_headers: dict):
        """Test that SHIP movement reduces stock."""
        # Create product, location, and stock item
        product_data = {"sku": f"SHIP-{uuid4().hex[:8]}", "name": "Ship Test Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        location_data = {"name": "Ship Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 100,
        }
        stock_response = await client.post(
            "/api/v1/stock-items/", json=stock_data, headers=auth_headers
        )
        stock_item_id = stock_response.json()["id"]

        # Create a SHIP movement
        movement_data = {
            "stockItemId": stock_item_id,
            "type": "SHIP",
            "quantity": 30,
            "reference": "ORD-001",
        }
        response = await client.post(
            "/api/v1/stock-movements/",
            json=movement_data,
            headers=auth_headers,
        )
        assert response.status_code == 201

        # Verify stock was reduced
        stock_response = await client.get(
            f"/api/v1/stock-items/{stock_item_id}",
            headers=auth_headers,
        )
        assert stock_response.json()["quantityAvailable"] == 70  # 100 - 30

    @pytest.mark.asyncio
    async def test_ship_insufficient_stock_rejected(self, client: AsyncClient, auth_headers: dict):
        """Test that SHIP with insufficient stock is rejected."""
        product_data = {"sku": f"INSUF-{uuid4().hex[:8]}", "name": "Insufficient Stock Product"}
        product_response = await client.post(
            "/api/v1/products/", json=product_data, headers=auth_headers
        )
        product_id = product_response.json()["id"]

        location_data = {"name": "Insufficient Location", "type": "WAREHOUSE"}
        location_response = await client.post(
            "/api/v1/locations/", json=location_data, headers=auth_headers
        )
        location_id = location_response.json()["id"]

        stock_data = {
            "productId": product_id,
            "locationId": location_id,
            "quantityAvailable": 10,
        }
        stock_response = await client.post(
            "/api/v1/stock-items/", json=stock_data, headers=auth_headers
        )
        stock_item_id = stock_response.json()["id"]

        # Try to ship more than available
        movement_data = {
            "stockItemId": stock_item_id,
            "type": "SHIP",
            "quantity": 50,
        }
        response = await client.post(
            "/api/v1/stock-movements/",
            json=movement_data,
            headers=auth_headers,
        )
        assert response.status_code == 400
        assert "Insufficient" in response.json()["detail"]
