"""Roles API endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy import func, select

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.permissions import ALL_PERMISSIONS
from src.db.models.role import Role
from src.db.models.user import User

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================

class RoleCreate(BaseModel):
    """Schema for creating a role."""
    name: str
    description: str | None = None
    permissions: List[str]

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        invalid = [
            p for p in v
            if p not in ALL_PERMISSIONS and p != "*:*" and "*" not in p
        ]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")
        return v


class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: str | None = None
    description: str | None = None
    permissions: List[str] | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str] | None) -> List[str] | None:
        if v is None:
            return v
        invalid = [
            p for p in v
            if p not in ALL_PERMISSIONS and p != "*:*" and "*" not in p
        ]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")
        return v


class RoleResponse(BaseModel):
    """Schema for role response."""
    id: UUID
    name: str
    description: str | None = None
    is_system: bool
    permissions: List[str]

    class Config:
        from_attributes = True


class RoleListResponse(BaseModel):
    """Schema for listing roles."""
    data: List[RoleResponse]
    total: int


# =============================================================================
# HELPER: Permission check (simplified for dev)
# =============================================================================

def require_permission(permission: str):
    """
    Dependency factory for permission-based access control.
    
    In development mode, this is bypassed.
    TODO: Implement full permission checking against user's roles.
    """
    async def permission_checker(
        user: User = Depends(get_current_user_with_dev_bypass),
    ) -> User:
        # For now, all authenticated users have access
        # Full RBAC implementation would check user.roles.permissions here
        return user
    
    return permission_checker


# =============================================================================
# CRUD ENDPOINTS
# =============================================================================

@router.post("/", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:create")),
):
    """Create a new role."""
    # Check for duplicate name within tenant
    result = await session.execute(
        select(Role).where(
            Role.tenant_id == user.tenant_id,
            Role.name == data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Role with this name already exists",
        )

    role = Role(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        permissions=data.permissions,
        is_system=False,
    )
    session.add(role)
    await session.commit()
    await session.refresh(role)
    return role


@router.get("/", response_model=RoleListResponse)
async def list_roles(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:view")),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all roles for the tenant."""
    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(Role).where(Role.tenant_id == user.tenant_id)
    )
    total = count_result.scalar_one()

    # Fetch roles
    offset = (page - 1) * page_size
    result = await session.execute(
        select(Role)
        .where(Role.tenant_id == user.tenant_id)
        .order_by(Role.name)
        .offset(offset)
        .limit(page_size)
    )
    roles = result.scalars().all()

    return RoleListResponse(
        data=[RoleResponse.model_validate(r) for r in roles],
        total=total,
    )


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:view")),
):
    """Get a single role by ID."""
    result = await session.execute(
        select(Role).where(
            Role.id == role_id,
            Role.tenant_id == user.tenant_id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    return role


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:edit")),
):
    """Update a role."""
    result = await session.execute(
        select(Role).where(
            Role.id == role_id,
            Role.tenant_id == user.tenant_id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify system roles",
        )

    if data.name is not None:
        # Check for duplicate name
        result = await session.execute(
            select(Role).where(
                Role.tenant_id == user.tenant_id,
                Role.name == data.name,
                Role.id != role_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Role with this name already exists",
            )
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions

    await session.commit()
    await session.refresh(role)
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:delete")),
):
    """Delete a role."""
    result = await session.execute(
        select(Role).where(
            Role.id == role_id,
            Role.tenant_id == user.tenant_id,
        )
    )
    role = result.scalar_one_or_none()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Role not found",
        )
    if role.is_system:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system roles",
        )

    await session.delete(role)
    await session.commit()
