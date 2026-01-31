"""Auth routes including tenant registration."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import get_user_manager, UserManager
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.db.session import get_session

router = APIRouter()


# Schemas for tenant registration
class TenantCreate(BaseModel):
    """Schema for creating a new tenant with admin user."""
    tenant_name: str
    tenant_slug: str
    email: EmailStr
    password: str
    first_name: str | None = None
    last_name: str | None = None


class TenantResponse(BaseModel):
    """Response after tenant creation."""
    tenant_id: UUID
    tenant_slug: str
    user_id: UUID
    email: str

    class Config:
        from_attributes = True


# Include fastapi-users auth routes
router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="",
)

# Include register route (for adding users to existing tenants)
# Note: This requires tenant_id, so we'll add a custom route instead

# Include password reset routes
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="",
)


@router.post("/register-tenant", response_model=TenantResponse)
async def register_tenant(
    data: TenantCreate,
    session: AsyncSession = Depends(get_session),
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Register a new tenant with an admin user.
    
    This creates both the tenant and the first admin user in one transaction.
    """
    # Check if tenant slug already exists
    existing = await session.execute(
        select(Tenant).where(Tenant.slug == data.tenant_slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Tenant slug already exists",
        )

    # Check if email already exists
    existing_user = await session.execute(
        select(User).where(User.email == data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create tenant
    tenant = Tenant(
        name=data.tenant_name,
        slug=data.tenant_slug,
    )
    session.add(tenant)
    await session.flush()  # Get tenant.id

    # Create admin user
    from fastapi_users.password import PasswordHelper
    password_helper = PasswordHelper()
    hashed_password = password_helper.hash(data.password)

    user = User(
        email=data.email,
        hashed_password=hashed_password,
        tenant_id=tenant.id,
        first_name=data.first_name,
        last_name=data.last_name,
        role="admin",
        is_active=True,
        is_superuser=False,
        is_verified=True,  # Auto-verify first admin
    )
    session.add(user)
    await session.commit()

    return TenantResponse(
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        user_id=user.id,
        email=user.email,
    )


@router.get("/me")
async def get_current_user_info(
    user: User = Depends(fastapi_users.current_user(active=True)),
):
    """Get current authenticated user info."""
    return {
        "id": str(user.id),
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "role": user.role,
        "tenant_id": str(user.tenant_id),
    }
