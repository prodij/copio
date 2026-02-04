"""API key management endpoints."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from passlib.hash import argon2
from pydantic import BaseModel
from sqlalchemy import func, select

from src.api.deps import CurrentUser, DbSession
from src.db.models.api_key import ApiKey
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


class ApiKeyCreate(BaseModel):
    """Request schema for creating an API key."""

    name: str
    expires_in_days: int | None = None  # None = never expires


class ApiKeyResponse(BaseModel):
    """Response schema for API key (excludes secret)."""

    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class ApiKeyCreated(ApiKeyResponse):
    """Response when creating a key - includes full key (shown only once)."""

    key: str


@router.post("", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """
    Create a new API key.

    The full key is only returned once at creation time.
    Store it securely - it cannot be retrieved again.
    """
    # Generate key: ck_live_<32 random chars>
    random_part = secrets.token_urlsafe(24)
    full_key = f"ck_live_{random_part}"
    prefix = full_key[:12]
    key_hash = argon2.hash(full_key)

    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    api_key = ApiKey(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=data.name,
        key_prefix=prefix,
        key_hash=key_hash,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=full_key,  # Only time this is returned!
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
    )


@router.get("", response_model=PaginatedResponse[ApiKeyResponse])
async def list_api_keys(
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all active (non-revoked) API keys for the current user."""
    query = select(ApiKey).where(
        ApiKey.user_id == current_user.id,
        ApiKey.revoked_at.is_(None),
    )

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    result = await session.execute(
        query.order_by(ApiKey.created_at.desc()).offset(offset).limit(page_size)
    )
    keys = result.scalars().all()

    return PaginatedResponse(
        data=[ApiKeyResponse.model_validate(k) for k in keys],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """
    Revoke an API key.

    The key will immediately stop working for authentication.
    """
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if api_key.revoked_at is not None:
        raise HTTPException(status_code=400, detail="API key already revoked")

    api_key.revoked_at = datetime.now(timezone.utc)
    await session.commit()
