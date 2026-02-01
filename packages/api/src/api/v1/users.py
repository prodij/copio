"""Users API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users.password import PasswordHelper
from pydantic import BaseModel, EmailStr
from sqlalchemy import select, delete

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.dependencies import require_permission
from src.db.models.user import User
from src.db.models.user_invite import UserInvite
from src.db.models.user_role import UserRole
from src.db.models.role import Role

router = APIRouter(prefix="/users", tags=["users"])

# Password helper for hashing
password_helper = PasswordHelper()


class UserResponse(BaseModel):
    """Response schema for user data."""
    id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    is_active: bool
    
    class Config:
        from_attributes = True


class UserInviteCreate(BaseModel):
    """Request schema for creating user invite."""
    email: EmailStr
    role_id: UUID


class UserInviteResponse(BaseModel):
    """Response schema for user invite (excludes token)."""
    id: UUID
    email: str
    role_id: UUID
    expires_at: datetime
    
    class Config:
        from_attributes = True


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    user: User = Depends(get_current_user_with_dev_bypass),
):
    """Get the currently authenticated user."""
    return user


@router.get("", response_model=List[UserResponse])
async def list_users(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("users:view")),
):
    """List all users in the current tenant."""
    result = await session.execute(
        select(User).where(User.tenant_id == user.tenant_id).order_by(User.email)
    )
    return result.scalars().all()


@router.post("/invite", response_model=UserInviteResponse, status_code=status.HTTP_201_CREATED)
async def invite_user(
    data: UserInviteCreate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("users:invite")),
):
    """
    Invite a new user to the tenant.
    
    Creates an invite record with a secure token that expires in 7 days.
    The token is not returned in the response for security.
    """
    # Check if email already exists in tenant
    existing = await session.execute(
        select(User).where(User.email == data.email).where(User.tenant_id == user.tenant_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    
    # Verify role exists and belongs to tenant
    role_result = await session.execute(
        select(Role).where(Role.id == data.role_id).where(Role.tenant_id == user.tenant_id)
    )
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found")
    
    invite = UserInvite(
        tenant_id=user.tenant_id,
        email=data.email,
        role_id=data.role_id,
        invited_by=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    session.add(invite)
    await session.commit()
    await session.refresh(invite)
    
    # TODO: Send email with invite link
    
    return invite


class InviteAccept(BaseModel):
    """Request schema for accepting an invite."""
    password: str
    first_name: str | None = None
    last_name: str | None = None


@router.get("/invite/{token}")
async def validate_invite(token: str, session: DbSession):
    """Validate an invite token and return invite details."""
    result = await session.execute(
        select(UserInvite).where(UserInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if not invite.is_valid:
        raise HTTPException(status_code=410, detail="Invite expired or already used")
    return {"email": invite.email, "expires_at": invite.expires_at}


@router.post("/invite/{token}/accept", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def accept_invite(token: str, data: InviteAccept, session: DbSession):
    """Accept an invite and create user account."""
    result = await session.execute(
        select(UserInvite).where(UserInvite.token == token)
    )
    invite = result.scalar_one_or_none()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")
    if not invite.is_valid:
        raise HTTPException(status_code=410, detail="Invite expired or already used")
    
    # Create user with hashed password
    user = User(
        email=invite.email,
        hashed_password=password_helper.hash(data.password),
        tenant_id=invite.tenant_id,
        first_name=data.first_name,
        last_name=data.last_name,
        is_active=True,
        is_verified=True,
    )
    session.add(user)
    await session.flush()  # Get user.id for UserRole
    
    # Assign role
    user_role = UserRole(user_id=user.id, role_id=invite.role_id)
    session.add(user_role)
    
    # Mark invite as accepted
    invite.accepted_at = datetime.now(timezone.utc)
    
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/{user_id}/roles/{role_id}")
async def assign_role_to_user(
    user_id: UUID,
    role_id: UUID,
    session: DbSession,
    current_user: User = Depends(get_current_user_with_dev_bypass),
):
    """Assign a role to a user."""
    # Verify user exists and belongs to same tenant
    result = await session.execute(
        select(User).where(User.id == user_id).where(User.tenant_id == current_user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify role exists and belongs to tenant
    role_result = await session.execute(
        select(Role).where(Role.id == role_id).where(Role.tenant_id == current_user.tenant_id)
    )
    if not role_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if user already has this role
    existing = await session.execute(
        select(UserRole).where(UserRole.user_id == user_id).where(UserRole.role_id == role_id)
    )
    if existing.scalar_one_or_none():
        return {"message": "Role already assigned"}
    
    # Assign role
    user_role = UserRole(user_id=user_id, role_id=role_id)
    session.add(user_role)
    await session.commit()
    
    return {"message": "Role assigned successfully"}


@router.delete("/{user_id}/roles/{role_id}")
async def remove_role_from_user(
    user_id: UUID,
    role_id: UUID,
    session: DbSession,
    current_user: User = Depends(get_current_user_with_dev_bypass),
):
    """Remove a role from a user."""
    # Verify user exists and belongs to same tenant
    result = await session.execute(
        select(User).where(User.id == user_id).where(User.tenant_id == current_user.tenant_id)
    )
    target_user = result.scalar_one_or_none()
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Find and delete the user role
    result = await session.execute(
        select(UserRole).where(UserRole.user_id == user_id).where(UserRole.role_id == role_id)
    )
    user_role = result.scalar_one_or_none()
    if not user_role:
        raise HTTPException(status_code=404, detail="User does not have this role")
    
    await session.delete(user_role)
    await session.commit()
    
    return {"message": "Role removed successfully"}


class UserUpdate(BaseModel):
    """Request schema for updating user."""
    first_name: str | None = None
    last_name: str | None = None
    role_id: UUID | None = None


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    session: DbSession,
    current_user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("users:edit")),
):
    """Update a user's details or role."""
    result = await session.execute(
        select(User).where(User.id == user_id).where(User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if data.first_name is not None:
        user.first_name = data.first_name
    if data.last_name is not None:
        user.last_name = data.last_name
    if data.role_id is not None:
        # Verify role exists
        role_result = await session.execute(
            select(Role).where(Role.id == data.role_id).where(Role.tenant_id == current_user.tenant_id)
        )
        if not role_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Role not found")
        
        # Update user role (remove old, add new)
        await session.execute(
            delete(UserRole).where(UserRole.user_id == user_id)
        )
        user_role = UserRole(user_id=user_id, role_id=data.role_id)
        session.add(user_role)
    
    await session.commit()
    await session.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_user(
    user_id: UUID,
    session: DbSession,
    current_user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("users:delete")),
):
    """Deactivate a user (soft delete)."""
    result = await session.execute(
        select(User).where(User.id == user_id).where(User.tenant_id == current_user.tenant_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    
    user.is_active = False
    await session.commit()
