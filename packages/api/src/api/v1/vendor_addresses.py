"""Vendor addresses API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.deps import DbSession, CurrentUser
from src.db.models import VendorAddress, Vendor
from src.schemas.common import PaginatedResponse, Pagination
from src.schemas.vendor import (
    VendorAddressCreate,
    VendorAddressUpdate,
    VendorAddressRead,
)

router = APIRouter()


@router.get("/by-vendor/{vendor_id}", response_model=PaginatedResponse[VendorAddressRead])
async def list_vendor_addresses(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List addresses for a vendor."""
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

    # Base query conditions
    base_conditions = [VendorAddress.vendor_id == vendor_id]

    # Count query
    count_query = select(func.count()).select_from(VendorAddress).where(*base_conditions)
    total = (await session.execute(count_query)).scalar() or 0

    # Data query with pagination
    result = await session.execute(
        select(VendorAddress)
        .where(*base_conditions)
        .order_by(VendorAddress.is_primary.desc(), VendorAddress.type)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse(
        data=items,
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.post("/", response_model=VendorAddressRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_address(
    vendor_id: UUID,
    data: VendorAddressCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new vendor address."""
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

    # If setting as primary, unset other primary addresses
    if data.is_primary:
        result = await session.execute(
            select(VendorAddress).where(
                VendorAddress.vendor_id == vendor_id,
                VendorAddress.is_primary == True,
            )
        )
        for addr in result.scalars():
            addr.is_primary = False

    address = VendorAddress(
        vendor_id=vendor_id,
        **data.model_dump(by_alias=False),
    )
    session.add(address)
    await session.commit()
    await session.refresh(address)
    return address


@router.get("/{address_id}", response_model=VendorAddressRead)
async def get_vendor_address(
    address_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single vendor address."""
    result = await session.execute(
        select(VendorAddress)
        .join(Vendor)
        .where(
            VendorAddress.id == address_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return address


@router.patch("/{address_id}", response_model=VendorAddressRead)
async def update_vendor_address(
    address_id: UUID,
    data: VendorAddressUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a vendor address."""
    result = await session.execute(
        select(VendorAddress)
        .join(Vendor)
        .where(
            VendorAddress.id == address_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    # If setting as primary, unset other primary addresses
    if data.is_primary:
        result = await session.execute(
            select(VendorAddress).where(
                VendorAddress.vendor_id == address.vendor_id,
                VendorAddress.is_primary == True,
                VendorAddress.id != address_id,
            )
        )
        for other_addr in result.scalars():
            other_addr.is_primary = False

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(address, field, value)

    await session.commit()
    await session.refresh(address)
    return address


@router.delete("/{address_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_address(
    address_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a vendor address."""
    result = await session.execute(
        select(VendorAddress)
        .join(Vendor)
        .where(
            VendorAddress.id == address_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    address = result.scalar_one_or_none()
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    await session.delete(address)
    await session.commit()
