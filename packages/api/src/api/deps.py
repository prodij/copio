"""API dependencies for dependency injection."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.session import get_session, set_tenant_context
from src.db.models.user import User
from src.auth import current_active_user as _current_active_user


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_with_dev_bypass(
    request: Request,
    session: DbSession,
) -> User:
    """
    Get current user with development bypass.
    
    In development mode, if no auth header is provided, returns the first
    active user from the database. This allows testing without auth.
    
    TODO: Remove dev bypass before production.
    """
    auth_header = request.headers.get("Authorization")
    
    # Development bypass - use first active user when no auth
    if settings.debug and not auth_header:
        result = await session.execute(
            select(User).where(User.is_active == True).limit(1)
        )
        dev_user = result.scalar_one_or_none()
        if dev_user:
            return dev_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No active users in database for dev bypass",
        )
    
    # Normal auth flow - delegate to fastapi-users
    return await _current_active_user(request)


# Type alias for current user dependency (with dev bypass)
CurrentUser = Annotated[User, Depends(get_current_user_with_dev_bypass)]


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """
    async def role_checker(
        current_user: CurrentUser,
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user
    
    return role_checker


async def get_tenant_session(
    session: DbSession,
    current_user: CurrentUser,
) -> AsyncSession:
    """
    Get database session with tenant context set.
    
    This should be used for all tenant-scoped queries to ensure RLS works.
    """
    await set_tenant_context(session, str(current_user.tenant_id))
    return session


# Type alias for tenant-scoped session
TenantSession = Annotated[AsyncSession, Depends(get_tenant_session)]
