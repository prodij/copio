"""Vendor contacts API endpoints (standalone)."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from src.api.deps import DbSession, CurrentUser
from src.db.models import VendorContact, Vendor
from src.schemas.vendor import (
    VendorContactUpdate,
    VendorContactRead,
)

router = APIRouter()


@router.get("/{contact_id}", response_model=VendorContactRead)
async def get_vendor_contact(
    contact_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single vendor contact."""
    result = await session.execute(
        select(VendorContact)
        .join(Vendor)
        .where(
            VendorContact.id == contact_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    return contact


@router.patch("/{contact_id}", response_model=VendorContactRead)
async def update_vendor_contact(
    contact_id: UUID,
    data: VendorContactUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a vendor contact."""
    result = await session.execute(
        select(VendorContact)
        .join(Vendor)
        .where(
            VendorContact.id == contact_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    # If setting as primary, unset other primary contacts
    if data.is_primary:
        result = await session.execute(
            select(VendorContact).where(
                VendorContact.vendor_id == contact.vendor_id,
                VendorContact.is_primary == True,
                VendorContact.id != contact_id,
            )
        )
        for other_contact in result.scalars():
            other_contact.is_primary = False

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(contact, field, value)

    await session.commit()
    await session.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_contact(
    contact_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a vendor contact."""
    result = await session.execute(
        select(VendorContact)
        .join(Vendor)
        .where(
            VendorContact.id == contact_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    contact = result.scalar_one_or_none()
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )

    await session.delete(contact)
    await session.commit()
