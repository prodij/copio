"""Vendor products API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.db.models import VendorProduct, Vendor, Product
from src.schemas.vendor import (
    VendorProductCreate,
    VendorProductUpdate,
    VendorProductRead,
)

router = APIRouter()


@router.get("/by-vendor/{vendor_id}", response_model=list[VendorProductRead])
async def list_vendor_products(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    active: bool | None = Query(None),
):
    """List products for a vendor."""
    # Verify vendor exists
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )

    query = (
        select(VendorProduct)
        .where(VendorProduct.vendor_id == vendor_id)
        .options(selectinload(VendorProduct.product))
    )

    if active is not None:
        query = query.where(VendorProduct.is_active == active)

    query = query.order_by(VendorProduct.is_preferred.desc(), VendorProduct.created_at)
    result = await session.execute(query)
    return result.scalars().all()


@router.get("/by-product/{product_id}", response_model=list[VendorProductRead])
async def list_product_vendors(
    product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """List vendors that supply a product."""
    # Verify product exists
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    result = await session.execute(
        select(VendorProduct)
        .where(
            VendorProduct.product_id == product_id,
            VendorProduct.is_active == True,
        )
        .options(selectinload(VendorProduct.product))
        .order_by(VendorProduct.is_preferred.desc(), VendorProduct.unit_cost)
    )
    return result.scalars().all()


@router.post("/", response_model=VendorProductRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_product(
    vendor_id: UUID,
    data: VendorProductCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a vendor-product relationship."""
    # Verify vendor exists
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )

    # Verify product exists
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

    # Check for existing relationship
    result = await session.execute(
        select(VendorProduct).where(
            VendorProduct.vendor_id == vendor_id,
            VendorProduct.product_id == data.product_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor-product relationship already exists",
        )

    # Check for duplicate vendor SKU
    result = await session.execute(
        select(VendorProduct).where(
            VendorProduct.vendor_id == vendor_id,
            VendorProduct.vendor_sku == data.vendor_sku,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Vendor SKU already exists for this vendor",
        )

    vendor_product = VendorProduct(
        vendor_id=vendor_id,
        **data.model_dump(by_alias=False),
    )
    session.add(vendor_product)
    await session.commit()

    # Reload with product
    result = await session.execute(
        select(VendorProduct)
        .options(selectinload(VendorProduct.product))
        .where(VendorProduct.id == vendor_product.id)
    )
    return result.scalar_one()


@router.get("/{vendor_product_id}", response_model=VendorProductRead)
async def get_vendor_product(
    vendor_product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single vendor-product relationship."""
    result = await session.execute(
        select(VendorProduct)
        .join(Vendor)
        .where(
            VendorProduct.id == vendor_product_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
        .options(selectinload(VendorProduct.product))
    )
    vendor_product = result.scalar_one_or_none()
    if not vendor_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor product not found",
        )
    return vendor_product


@router.patch("/{vendor_product_id}", response_model=VendorProductRead)
async def update_vendor_product(
    vendor_product_id: UUID,
    data: VendorProductUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a vendor-product relationship."""
    result = await session.execute(
        select(VendorProduct)
        .join(Vendor)
        .where(
            VendorProduct.id == vendor_product_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor_product = result.scalar_one_or_none()
    if not vendor_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor product not found",
        )

    # Check for duplicate vendor SKU if changing
    if data.vendor_sku and data.vendor_sku != vendor_product.vendor_sku:
        result = await session.execute(
            select(VendorProduct).where(
                VendorProduct.vendor_id == vendor_product.vendor_id,
                VendorProduct.vendor_sku == data.vendor_sku,
                VendorProduct.id != vendor_product_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vendor SKU already exists for this vendor",
            )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(vendor_product, field, value)

    await session.commit()

    # Reload with product
    result = await session.execute(
        select(VendorProduct)
        .options(selectinload(VendorProduct.product))
        .where(VendorProduct.id == vendor_product_id)
    )
    return result.scalar_one()


@router.delete("/{vendor_product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_product(
    vendor_product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a vendor-product relationship."""
    result = await session.execute(
        select(VendorProduct)
        .join(Vendor)
        .where(
            VendorProduct.id == vendor_product_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor_product = result.scalar_one_or_none()
    if not vendor_product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor product not found",
        )

    await session.delete(vendor_product)
    await session.commit()
