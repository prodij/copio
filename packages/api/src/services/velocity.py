"""Velocity calculation service."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession


async def calculate_listing_velocity(
    session: AsyncSession,
    tenant_id: UUID,
    listing_id: UUID,
    as_of: datetime | None = None,
) -> dict:
    """
    Calculate velocity metrics for a single listing.
    
    Args:
        session: Database session
        tenant_id: Tenant UUID
        listing_id: Listing UUID
        as_of: Calculate as of this datetime (default: now)
    
    Returns:
        Dict with velocity_1d, velocity_7d, velocity_30d, trend_7d_30d
    """
    if as_of is None:
        as_of = datetime.utcnow()
    
    # TODO: Implement after Order/OrderLine models are mapped
    # This is a placeholder showing the intended logic
    
    # date_1d = as_of - timedelta(days=1)
    # date_7d = as_of - timedelta(days=7)
    # date_30d = as_of - timedelta(days=30)
    
    # Query would be:
    # SELECT 
    #   SUM(CASE WHEN placed_at >= date_1d THEN quantity END) as sales_1d,
    #   SUM(CASE WHEN placed_at >= date_7d THEN quantity END) as sales_7d,
    #   SUM(quantity) as sales_30d
    # FROM order_lines ol
    # JOIN orders o ON ol.order_id = o.id
    # WHERE ol.listing_id = listing_id
    #   AND o.placed_at >= date_30d
    #   AND o.tenant_id = tenant_id
    
    return {
        "listing_id": str(listing_id),
        "velocity_1d": Decimal("0"),
        "velocity_7d": Decimal("0"),
        "velocity_30d": Decimal("0"),
        "trend_7d_30d": None,
        "calculated_at": as_of.isoformat(),
    }


async def calculate_all_velocities(
    session: AsyncSession,
    tenant_id: UUID,
) -> int:
    """
    Calculate velocity for all active listings for a tenant.
    
    Args:
        session: Database session
        tenant_id: Tenant UUID
    
    Returns:
        Number of listings processed
    """
    # TODO: Implement after models are ready
    # 1. Get all active listings for tenant
    # 2. Calculate velocity for each
    # 3. Bulk insert into listing_velocity table
    return 0


async def calculate_sku_consumption(
    session: AsyncSession,
    tenant_id: UUID,
) -> int:
    """
    Calculate SKU consumption rates from listing velocities.
    
    Args:
        session: Database session
        tenant_id: Tenant UUID
    
    Returns:
        Number of SKUs processed
    """
    # TODO: Implement after ListingSkuMapping model exists
    # 1. For each SKU, find all listings containing it
    # 2. Sum: listing_velocity × quantity_per_unit
    # 3. Calculate days_of_stock
    # 4. Set reorder_urgency
    return 0
