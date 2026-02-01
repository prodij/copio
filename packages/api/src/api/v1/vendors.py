"""Vendors API endpoints."""

from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.auth.dependencies import require_permission
from src.db.models import (
    Vendor,
    VendorContact,
    VendorProduct,
    PurchaseOrder,
    VendorTier,
)
from src.schemas.vendor import (
    VendorCreate,
    VendorUpdate,
    VendorRead,
    VendorListItem,
    VendorStatsSummary,
    VendorContactCreate,
    VendorContactRead,
)

router = APIRouter()


# =============================================================================
# VENDOR CRUD
# =============================================================================

@router.post("/", response_model=VendorRead, status_code=status.HTTP_201_CREATED)
async def create_vendor(
    data: VendorCreate,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("vendors:create")),
):
    """Create a new vendor."""
    # Check for duplicate code
    if data.code:
        existing = await session.execute(
            select(Vendor).where(Vendor.code == data.code)
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vendor code already exists",
            )

    vendor = Vendor(
        tenant_id=current_user.tenant_id,
        **data.model_dump(by_alias=False, exclude_none=True),
    )
    session.add(vendor)
    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(Vendor)
        .options(
            selectinload(Vendor.contacts),
            selectinload(Vendor.addresses),
            selectinload(Vendor.documents),
            selectinload(Vendor.products),
        )
        .where(Vendor.id == vendor.id)
    )
    return result.scalar_one()


@router.get("/", response_model=list[VendorListItem])
async def list_vendors(
    session: DbSession,
    current_user: CurrentUser,
    active: bool | None = Query(None),
    tier: VendorTier | None = None,
    search: str | None = None,
    _perm=Depends(require_permission("vendors:view")),
):
    """List vendors with optional filtering."""
    query = select(Vendor).where(Vendor.tenant_id == current_user.tenant_id)

    if active is not None:
        query = query.where(Vendor.is_active == active)
    if tier:
        query = query.where(Vendor.tier == tier)
    if search:
        search_filter = or_(
            Vendor.name.ilike(f"%{search}%"),
            Vendor.code.ilike(f"%{search}%"),
            Vendor.legal_name.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    query = query.options(
        selectinload(Vendor.contacts),
    ).order_by(Vendor.name)

    result = await session.execute(query)
    vendors = result.scalars().all()

    # Get counts for each vendor
    vendor_list = []
    for vendor in vendors:
        # Get product and PO counts
        product_count = await session.execute(
            select(func.count()).where(VendorProduct.vendor_id == vendor.id)
        )
        po_count = await session.execute(
            select(func.count()).where(PurchaseOrder.vendor_id == vendor.id)
        )
        
        vendor_item = VendorListItem(
            id=vendor.id,
            name=vendor.name,
            code=vendor.code,
            tier=vendor.tier,
            is_active=vendor.is_active,
            lead_time_days=vendor.lead_time_days,
            contacts=[VendorContactRead.model_validate(c) for c in vendor.contacts if c.is_active and c.is_primary][:1],
            product_count=product_count.scalar_one(),
            po_count=po_count.scalar_one(),
        )
        vendor_list.append(vendor_item)

    return vendor_list


@router.get("/stats/summary", response_model=VendorStatsSummary)
async def get_vendor_stats(
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("vendors:view")),
):
    """Get vendor statistics summary."""
    # Total active vendors
    total_result = await session.execute(
        select(func.count()).where(
            Vendor.tenant_id == current_user.tenant_id,
            Vendor.is_active == True,
        )
    )
    total = total_result.scalar_one()

    # By tier
    tier_result = await session.execute(
        select(Vendor.tier, func.count())
        .where(
            Vendor.tenant_id == current_user.tenant_id,
            Vendor.is_active == True,
        )
        .group_by(Vendor.tier)
    )
    by_tier = {str(tier.value): count for tier, count in tier_result.all()}

    # Contracts expiring in 30 days
    expiring_soon = await session.execute(
        select(func.count()).where(
            Vendor.tenant_id == current_user.tenant_id,
            Vendor.is_active == True,
            Vendor.contract_end_date >= datetime.now(),
            Vendor.contract_end_date <= datetime.now() + timedelta(days=30),
        )
    )

    return VendorStatsSummary(
        total=total,
        by_tier=by_tier,
        contracts_expiring_soon=expiring_soon.scalar_one(),
    )


@router.get("/{vendor_id}", response_model=VendorRead)
async def get_vendor(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("vendors:view")),
):
    """Get a single vendor with all relationships."""
    result = await session.execute(
        select(Vendor)
        .options(
            selectinload(Vendor.contacts),
            selectinload(Vendor.addresses),
            selectinload(Vendor.documents),
            selectinload(Vendor.products).selectinload(VendorProduct.product),
        )
        .where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )
    return vendor


@router.patch("/{vendor_id}", response_model=VendorRead)
async def update_vendor(
    vendor_id: UUID,
    data: VendorUpdate,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("vendors:edit")),
):
    """Update a vendor."""
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )

    # Check for duplicate code
    if data.code and data.code != vendor.code:
        existing = await session.execute(
            select(Vendor).where(
                Vendor.code == data.code,
                Vendor.id != vendor_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Vendor code already exists",
            )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    # Handle empty strings for optional fields
    for field in ["website", "account_manager_email"]:
        if field in update_data and update_data[field] == "":
            update_data[field] = None

    for field, value in update_data.items():
        setattr(vendor, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(Vendor)
        .options(
            selectinload(Vendor.contacts),
            selectinload(Vendor.addresses),
            selectinload(Vendor.documents),
            selectinload(Vendor.products),
        )
        .where(Vendor.id == vendor_id)
    )
    return result.scalar_one()


@router.delete("/{vendor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("vendors:delete")),
):
    """Delete a vendor."""
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )

    # Check for purchase orders
    po_count = await session.execute(
        select(func.count()).where(PurchaseOrder.vendor_id == vendor_id)
    )
    if po_count.scalar_one() > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete vendor with purchase orders",
        )

    await session.delete(vendor)
    await session.commit()


# =============================================================================
# VENDOR CONTACTS (Nested under vendors)
# =============================================================================

@router.get("/{vendor_id}/contacts", response_model=list[VendorContactRead])
async def list_vendor_contacts(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """List contacts for a vendor."""
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

    result = await session.execute(
        select(VendorContact)
        .where(VendorContact.vendor_id == vendor_id)
        .order_by(VendorContact.is_primary.desc(), VendorContact.role, VendorContact.name)
    )
    return result.scalars().all()


@router.post("/{vendor_id}/contacts", response_model=VendorContactRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_contact(
    vendor_id: UUID,
    data: VendorContactCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Add a contact to a vendor."""
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

    # If setting as primary, unset other primary contacts
    if data.is_primary:
        await session.execute(
            select(VendorContact)
            .where(
                VendorContact.vendor_id == vendor_id,
                VendorContact.is_primary == True,
            )
        )
        result = await session.execute(
            select(VendorContact).where(
                VendorContact.vendor_id == vendor_id,
                VendorContact.is_primary == True,
            )
        )
        for contact in result.scalars():
            contact.is_primary = False

    contact = VendorContact(
        vendor_id=vendor_id,
        **data.model_dump(by_alias=False),
    )
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
    return contact
