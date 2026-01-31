"""Vendor documents API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from src.api.deps import DbSession, CurrentUser
from src.db.models import VendorDocument, Vendor, DocumentType
from src.schemas.vendor import (
    VendorDocumentCreate,
    VendorDocumentUpdate,
    VendorDocumentRead,
)

router = APIRouter()


@router.get("/by-vendor/{vendor_id}", response_model=list[VendorDocumentRead])
async def list_vendor_documents(
    vendor_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    type: DocumentType | None = None,
    active: bool | None = Query(None),
):
    """List documents for a vendor."""
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

    query = select(VendorDocument).where(VendorDocument.vendor_id == vendor_id)

    if type:
        query = query.where(VendorDocument.type == type)
    if active is not None:
        query = query.where(VendorDocument.is_active == active)

    query = query.order_by(VendorDocument.type, VendorDocument.uploaded_at.desc())
    result = await session.execute(query)
    return result.scalars().all()


@router.post("/", response_model=VendorDocumentRead, status_code=status.HTTP_201_CREATED)
async def create_vendor_document(
    vendor_id: UUID,
    data: VendorDocumentCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new vendor document."""
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

    document = VendorDocument(
        vendor_id=vendor_id,
        uploaded_by=str(current_user.id),
        **data.model_dump(by_alias=False),
    )
    session.add(document)
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/{document_id}", response_model=VendorDocumentRead)
async def get_vendor_document(
    document_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single vendor document."""
    result = await session.execute(
        select(VendorDocument)
        .join(Vendor)
        .where(
            VendorDocument.id == document_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    return document


@router.patch("/{document_id}", response_model=VendorDocumentRead)
async def update_vendor_document(
    document_id: UUID,
    data: VendorDocumentUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a vendor document."""
    result = await session.execute(
        select(VendorDocument)
        .join(Vendor)
        .where(
            VendorDocument.id == document_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(document, field, value)

    await session.commit()
    await session.refresh(document)
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vendor_document(
    document_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a vendor document."""
    result = await session.execute(
        select(VendorDocument)
        .join(Vendor)
        .where(
            VendorDocument.id == document_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    await session.delete(document)
    await session.commit()
