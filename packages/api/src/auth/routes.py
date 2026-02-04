"""Auth routes including tenant registration and user management."""

from datetime import datetime, timedelta, timezone
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.email import send_invite_email

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import get_user_manager, UserManager
from src.auth.default_roles import DEFAULT_ROLES, get_owner_role
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.db.models.role import Role
from src.db.models.user_role import UserRole
from src.db.session import get_session

router = APIRouter()
password_helper = PasswordHelper()

# Current user dependency (avoiding circular import)
current_active_user = fastapi_users.current_user(active=True)


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """
    async def role_checker(
        current_user: User = Depends(current_active_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    
    return role_checker


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
    await session.flush()  # Get user.id

    # Create all default roles for the tenant
    owner_role = None
    for role_def in DEFAULT_ROLES:
        role = Role(
            tenant_id=tenant.id,
            name=role_def["name"],
            description=role_def["description"],
            is_system=role_def["is_system"],
            permissions=role_def["permissions"],
        )
        session.add(role)
        if role_def["name"] == "Owner":
            await session.flush()  # Get owner role id
            owner_role = role
    
    # Assign Owner role to the first user (tenant creator)
    if owner_role:
        user_role = UserRole(
            user_id=user.id,
            role_id=owner_role.id,
        )
        session.add(user_role)
    
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
        "is_active": user.is_active,
        "is_verified": user.is_verified,
    }


# =============================================================================
# Profile Management Endpoints
# =============================================================================


class UpdateProfileRequest(BaseModel):
    """Schema for updating user profile."""
    first_name: str | None = None
    last_name: str | None = None


class UpdateProfileResponse(BaseModel):
    """Response after profile update."""
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    role: str
    tenant_id: str


@router.patch("/me", response_model=UpdateProfileResponse)
async def update_profile(
    data: UpdateProfileRequest,
    user: User = Depends(fastapi_users.current_user(active=True)),
    session: AsyncSession = Depends(get_session),
):
    """Update the current user's profile (first_name, last_name)."""
    update_data = {}
    if data.first_name is not None:
        update_data["first_name"] = data.first_name
    if data.last_name is not None:
        update_data["last_name"] = data.last_name
    
    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    
    await session.execute(
        update(User).where(User.id == user.id).values(**update_data)
    )
    await session.commit()
    
    # Refresh user to get updated values
    await session.refresh(user)
    
    return UpdateProfileResponse(
        id=str(user.id),
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        tenant_id=str(user.tenant_id),
    )


class ChangePasswordRequest(BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.post("/change-password")
async def change_password(
    data: ChangePasswordRequest,
    user: User = Depends(fastapi_users.current_user(active=True)),
    session: AsyncSession = Depends(get_session),
):
    """Change the current user's password."""
    # Verify current password
    valid, _ = password_helper.verify_and_update(data.current_password, user.hashed_password)
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current password",
        )
    
    # Hash and set new password
    new_hashed = password_helper.hash(data.new_password)
    await session.execute(
        update(User).where(User.id == user.id).values(hashed_password=new_hashed)
    )
    await session.commit()
    
    return {"message": "Password changed successfully"}


@router.delete("/me")
async def deactivate_account(
    user: User = Depends(fastapi_users.current_user(active=True)),
    session: AsyncSession = Depends(get_session),
):
    """Deactivate the current user's account."""
    await session.execute(
        update(User).where(User.id == user.id).values(is_active=False)
    )
    await session.commit()
    
    return {"message": "Account deactivated"}


# =============================================================================
# User Invitation Endpoints (Admin Only)
# =============================================================================


class InviteUserRequest(BaseModel):
    """Schema for inviting a user to the tenant."""
    email: EmailStr
    role: str = "member"  # 'admin' | 'member'
    first_name: str | None = None
    last_name: str | None = None


class InviteUserResponse(BaseModel):
    """Response after user invitation."""
    user_id: str
    email: str
    invite_token: str
    expires_at: str


class AcceptInviteRequest(BaseModel):
    """Schema for accepting an invitation."""
    token: str
    password: str = Field(..., min_length=8)


class AcceptInviteResponse(BaseModel):
    """Response after accepting invitation."""
    user_id: str
    email: str
    message: str


class CreateUserRequest(BaseModel):
    """Schema for directly creating a user (admin only)."""
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: str = "member"
    first_name: str | None = None
    last_name: str | None = None


class CreateUserResponse(BaseModel):
    """Response after user creation."""
    id: str
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    tenant_id: str


@router.post("/invite", response_model=InviteUserResponse)
async def invite_user(
    data: InviteUserRequest,
    admin: User = Depends(require_role(["admin"])),
    session: AsyncSession = Depends(get_session),
):
    """
    Invite a user to join the tenant (admin only).
    
    Creates an inactive user with an invite token. The user must accept
    the invitation by setting their password.
    """
    if data.role not in ("admin", "member"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'member'",
        )
    
    # Check if email already exists
    existing = await session.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Generate invite token and expiry
    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    # Create inactive user with invite token stored in hashed_password field temporarily
    # We store token hash + expiry in a special format: TOKEN:<hash>:<expiry_timestamp>
    token_data = f"INVITE:{password_helper.hash(invite_token)}:{int(expires_at.timestamp())}"
    
    user = User(
        email=data.email,
        hashed_password=token_data,
        tenant_id=admin.tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
        is_active=False,
        is_verified=False,
    )
    session.add(user)
    await session.commit()
    
    # Get tenant name for email
    result = await session.execute(
        select(Tenant).where(Tenant.id == admin.tenant_id)
    )
    tenant = result.scalar_one()
    
    # Send invite email
    # Note: In production, use a proper frontend URL from config
    invite_url = f"http://localhost:3000/accept-invite?token={invite_token}"
    
    await send_invite_email(
        to=data.email,
        tenant_name=tenant.name,
        inviter_name=admin.full_name,
        inviter_email=admin.email,
        role=data.role,
        invite_url=invite_url,
    )
    
    return InviteUserResponse(
        user_id=str(user.id),
        email=user.email,
        invite_token=invite_token,  # Also returned for testing/debugging
        expires_at=expires_at.isoformat(),
    )


@router.post("/accept-invite", response_model=AcceptInviteResponse)
async def accept_invite(
    data: AcceptInviteRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Accept an invitation and set password.
    
    This activates the user account and allows them to log in.
    """
    # Find all inactive users with invite tokens
    result = await session.execute(
        select(User).where(
            User.is_active == False,
            User.hashed_password.startswith("INVITE:"),
        )
    )
    users = result.scalars().all()
    
    # Find the user with matching token
    matched_user = None
    for user in users:
        parts = user.hashed_password.split(":", 2)
        if len(parts) != 3:
            continue
        
        _, token_hash, expiry_ts = parts
        
        # Check expiry
        try:
            expiry = datetime.fromtimestamp(int(expiry_ts), tz=timezone.utc)
            if datetime.now(timezone.utc) > expiry:
                continue
        except (ValueError, OSError):
            continue
        
        # Verify token
        valid, _ = password_helper.verify_and_update(data.token, token_hash)
        if valid:
            matched_user = user
            break
    
    if not matched_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired invite token",
        )
    
    # Activate user and set password
    hashed_password = password_helper.hash(data.password)
    await session.execute(
        update(User).where(User.id == matched_user.id).values(
            hashed_password=hashed_password,
            is_active=True,
            is_verified=True,
        )
    )
    await session.commit()
    
    return AcceptInviteResponse(
        user_id=str(matched_user.id),
        email=matched_user.email,
        message="Invitation accepted. You can now log in.",
    )


@router.post("/users", response_model=CreateUserResponse)
async def create_user(
    data: CreateUserRequest,
    admin: User = Depends(require_role(["admin"])),
    session: AsyncSession = Depends(get_session),
):
    """
    Directly create a user in the tenant (admin only).
    
    Use this instead of invite if you want to set the password immediately.
    """
    if data.role not in ("admin", "member"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be 'admin' or 'member'",
        )
    
    # Check if email already exists
    existing = await session.execute(
        select(User).where(User.email == data.email)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )
    
    # Create user
    hashed_password = password_helper.hash(data.password)
    user = User(
        email=data.email,
        hashed_password=hashed_password,
        tenant_id=admin.tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        role=data.role,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.commit()
    
    return CreateUserResponse(
        id=str(user.id),
        email=user.email,
        role=user.role,
        first_name=user.first_name,
        last_name=user.last_name,
        tenant_id=str(user.tenant_id),
    )


# =============================================================================
# Forgot Password Flow
# =============================================================================


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""
    token: str
    password: str = Field(..., min_length=8)


@router.post("/forgot-password")
async def forgot_password(
    data: ForgotPasswordRequest,
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Request a password reset.
    
    For now, the reset token is logged to console. In production,
    this should send an email.
    """
    try:
        user = await user_manager.get_by_email(data.email)
        token = await user_manager.forgot_password(user)
        # Token is logged in user_manager.on_after_forgot_password
        return {"message": "If the email exists, a reset link has been sent"}
    except Exception:
        # Don't reveal if email exists
        return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    data: ResetPasswordRequest,
    user_manager: UserManager = Depends(get_user_manager),
):
    """
    Reset password using the token from forgot-password.
    """
    try:
        await user_manager.reset_password(data.token, data.password)
        return {"message": "Password reset successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
