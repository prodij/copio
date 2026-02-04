"""Admin API endpoints for superuser-only operations."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.api.deps import DbSession, get_current_user
from src.db.models.user import User
from src.services import system_settings

router = APIRouter()


# =============================================================================
# SCHEMAS
# =============================================================================


class SystemSettingResponse(BaseModel):
    """Schema for system setting response."""

    id: UUID
    key: str
    value: dict
    description: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SystemSettingUpdate(BaseModel):
    """Schema for updating a system setting."""

    value: dict
    description: str | None = None


# =============================================================================
# DEPENDENCIES
# =============================================================================


async def require_superuser(
    user: User = Depends(get_current_user),
) -> User:
    """Require the current user to be a superuser."""
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser access required",
        )
    return user


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get("/settings", response_model=list[SystemSettingResponse])
async def list_settings(
    session: DbSession,
    _user: User = Depends(require_superuser),
):
    """List all system settings. Requires superuser."""
    settings = await system_settings.get_all_settings(session)
    return settings


@router.get("/settings/{key}", response_model=SystemSettingResponse)
async def get_setting(
    key: str,
    session: DbSession,
    _user: User = Depends(require_superuser),
):
    """Get a single system setting by key. Requires superuser."""
    from sqlalchemy import select
    from src.db.models.system_settings import SystemSettings

    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    return setting


@router.patch("/settings/{key}", response_model=SystemSettingResponse)
async def update_setting(
    key: str,
    data: SystemSettingUpdate,
    session: DbSession,
    _user: User = Depends(require_superuser),
):
    """Update a system setting. Requires superuser."""
    from sqlalchemy import select
    from src.db.models.system_settings import SystemSettings

    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Setting '{key}' not found",
        )

    setting.value = data.value
    if data.description is not None:
        setting.description = data.description

    await session.commit()
    await session.refresh(setting)

    # Invalidate cache
    system_settings.invalidate_cache(key)

    return setting
