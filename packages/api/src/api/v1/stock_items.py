"""Stock items API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.auth.dependencies import require_permission
from src.db.models import StockItem, Product, Location
from src.schemas.inventory import (
    StockItemCreate,
    StockItemUpdate,
    StockItemRead,
)

router = APIRouter()


@router.post("/", response_model=StockItemRead, status_code=status.HTTP_201_CREATED)
async def create_stock_item(
    data: StockItemCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new stock item."""
    # Verify product exists and belongs to tenant
    result = await session.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product not found",
        )

    # Verify location exists and belongs to tenant
    result = await session.execute(
        select(Location).where(
            Location.id == data.location_id,
            Location.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Location not found",
        )

    # Check for existing stock item
    result = await session.execute(
        select(StockItem).where(
            StockItem.product_id == data.product_id,
            StockItem.location_id == data.location_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Stock item already exists for this product and location",
        )

    stock_item = StockItem(
        tenant_id=current_user.tenant_id,
        **data.model_dump(by_alias=False, exclude_none=True),
    )
    session.add(stock_item)
    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(StockItem)
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
        .where(StockItem.id == stock_item.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[StockItemRead])
async def list_stock_items(
    session: DbSession,
    current_user: CurrentUser,
):
    """List all stock items for the tenant."""
    result = await session.execute(
        select(StockItem)
        .where(StockItem.tenant_id == current_user.tenant_id)
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
    )
    return result.scalars().all()


@router.get("/by-location/{location_id}", response_model=list[StockItemRead])
async def list_stock_items_by_location(
    location_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """List stock items for a specific location."""
    result = await session.execute(
        select(StockItem)
        .where(
            StockItem.location_id == location_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
    )
    return result.scalars().all()


@router.get("/by-product/{product_id}", response_model=list[StockItemRead])
async def list_stock_items_by_product(
    product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """List stock items for a specific product."""
    result = await session.execute(
        select(StockItem)
        .where(
            StockItem.product_id == product_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
    )
    return result.scalars().all()


@router.get("/{stock_item_id}", response_model=StockItemRead)
async def get_stock_item(
    stock_item_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single stock item."""
    result = await session.execute(
        select(StockItem)
        .where(
            StockItem.id == stock_item_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
    )
    stock_item = result.scalar_one_or_none()
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock item not found",
        )
    return stock_item


@router.patch("/{stock_item_id}", response_model=StockItemRead)
async def update_stock_item(
    stock_item_id: UUID,
    data: StockItemUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a stock item."""
    result = await session.execute(
        select(StockItem).where(
            StockItem.id == stock_item_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
    )
    stock_item = result.scalar_one_or_none()
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock item not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(stock_item, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(StockItem)
        .options(
            selectinload(StockItem.product),
            selectinload(StockItem.location),
        )
        .where(StockItem.id == stock_item_id)
    )
    return result.scalar_one()


@router.delete("/{stock_item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stock_item(
    stock_item_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a stock item."""
    result = await session.execute(
        select(StockItem).where(
            StockItem.id == stock_item_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
    )
    stock_item = result.scalar_one_or_none()
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock item not found",
        )

    await session.delete(stock_item)
    await session.commit()
