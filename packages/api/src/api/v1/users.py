"""Users API endpoints."""

from datetime import datetime, timedelta, timezone
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.dependencies import require_permission
from src.db.models.user import User
from src.db.models.user_invite import UserInvite
from src.db.models.role import Role

router = APIRouter(prefix="/users", tags=["users"])


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
