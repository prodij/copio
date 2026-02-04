"""API dependencies for dependency injection."""

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from passlib.hash import argon2
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models.user import User
from src.db.models.api_key import ApiKey
from src.auth.tokens import decode_access_token


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    session: DbSession,
) -> User:
    """
    Get current user from access_token cookie, Bearer token, or API key.

    Priority:
    1. API Key (Authorization: Bearer ck_...)
    2. Bearer token (Authorization: Bearer <jwt>)
    3. Access token cookie
    """
    auth_header = request.headers.get("Authorization")

    # Check for API key first
    if auth_header and auth_header.startswith("Bearer ck_"):
        api_key = auth_header.replace("Bearer ", "")
        return await _get_user_from_api_key(session, api_key)

    # Check for Bearer token in header
    access_token = None
    if auth_header and auth_header.startswith("Bearer "):
        access_token = auth_header.replace("Bearer ", "")

    # Fall back to cookie
    if not access_token:
        access_token = request.cookies.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Decode and validate token
    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Fetch user
    user_id = UUID(payload["sub"])
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def _get_user_from_api_key(session: AsyncSession, raw_key: str) -> User:
    """Validate API key and return associated user."""
    # Extract prefix (first 12 chars: ck_live_xxxx)
    if len(raw_key) < 12:
        raise HTTPException(status_code=401, detail="Invalid API key")

    prefix = raw_key[:12]

    # Find key by prefix
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    # Verify key hash
    if not argon2.verify(raw_key, api_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await session.commit()

    # Fetch user
    result = await session.execute(
        select(User).where(User.id == api_key.user_id, User.is_active)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# Type alias for current user dependency
CurrentUser = Annotated[User, Depends(get_current_user)]


# Keep TenantSession for backwards compatibility if used
async def get_tenant_session(
    session: DbSession,
    current_user: CurrentUser,
) -> AsyncSession:
    """Get database session with tenant context."""
    from src.db.session import set_tenant_context
    await set_tenant_context(session, str(current_user.tenant_id))
    return session


TenantSession = Annotated[AsyncSession, Depends(get_tenant_session)]
