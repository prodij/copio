"""Company profile API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.dependencies import require_permission
from src.db.models.user import User
from src.db.models.tenant import Tenant

router = APIRouter(prefix="/company", tags=["company"])


class CompanyProfileResponse(BaseModel):
    """Response schema for company profile."""
    id: UUID
    name: str
    slug: str
    timezone: str
    base_currency: str
    
    # Company identity
    company_name: str | None
    legal_name: str | None
    tax_id: str | None
    
    # Address
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    
    # Contact
    phone: str | None
    email: str | None
    website: str | None
    
    # Branding
    logo_url: str | None
    
    class Config:
        from_attributes = True


class CompanyProfileUpdate(BaseModel):
    """Request schema for updating company profile."""
    company_name: str | None = None
    legal_name: str | None = None
    tax_id: str | None = None
    
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    
    timezone: str | None = None
    base_currency: str | None = None


@router.get("", response_model=CompanyProfileResponse)
async def get_company_profile(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
):
    """Get the current company profile."""
    result = await session.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Company not found")
    return tenant


@router.patch("", response_model=CompanyProfileResponse)
async def update_company_profile(
    data: CompanyProfileUpdate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("company:edit")),
):
    """Update company profile settings."""
    result = await session.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=404, detail="Company not found")
    
    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(tenant, field, value)
    
    await session.commit()
    await session.refresh(tenant)
    
    return tenant
