"""API dependencies for dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session, set_tenant_context
from src.db.models.user import User


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


# Type alias for database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]


def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.
    
    Usage:
        @router.get("/admin-only")
        async def admin_endpoint(user: User = Depends(require_role(["admin"]))):
            ...
    """
    async def role_checker(
        # current_user: User = Depends(current_active_user),  # TODO: Enable after auth setup
    ) -> User:
        # TODO: Implement after fastapi-users setup
        # if current_user.role not in allowed_roles:
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Insufficient permissions",
        #     )
        # return current_user
        raise NotImplementedError("Auth not yet configured")
    
    return role_checker


async def get_tenant_session(
    session: DbSession,
    # current_user: User = Depends(current_active_user),  # TODO: Enable after auth setup
) -> AsyncSession:
    """
    Get database session with tenant context set.
    
    This should be used for all tenant-scoped queries to ensure RLS works.
    """
    # TODO: Get tenant_id from current_user after auth setup
    # await set_tenant_context(session, str(current_user.tenant_id))
    return session
