"""API dependencies for dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session, set_tenant_context
from src.db.models.user import User
from src.auth import current_active_user


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]

# Type alias for current user dependency
CurrentUser = Annotated[User, Depends(current_active_user)]


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
