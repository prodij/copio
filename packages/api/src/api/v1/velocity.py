"""Velocity API endpoints."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/listings")
async def list_listing_velocities():
    """Get velocity metrics for all listings."""
    # TODO: Implement after velocity models are created
    return {"message": "Velocity listings endpoint - not yet implemented"}


@router.get("/listings/{listing_id}")
async def get_listing_velocity(listing_id: str):
    """Get velocity metrics for a specific listing."""
    return {"listing_id": listing_id, "message": "Not yet implemented"}


@router.get("/skus")
async def list_sku_consumption():
    """Get consumption rates for all SKUs."""
    return {"message": "SKU consumption endpoint - not yet implemented"}


@router.get("/skus/{sku_id}")
async def get_sku_consumption(sku_id: str):
    """Get consumption rate for a specific SKU."""
    return {"sku_id": sku_id, "message": "Not yet implemented"}


@router.get("/dashboard")
async def velocity_dashboard():
    """Get velocity dashboard summary."""
    return {
        "total_listings": 0,
        "healthy": 0,
        "declining": 0,
        "dead_stock": 0,
        "message": "Dashboard endpoint - not yet implemented",
    }
