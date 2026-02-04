# packages/api/src/auth/dependencies.py
"""FastAPI dependencies for permission enforcement."""

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status

from src.api.deps import DbSession, get_current_user
from src.auth.enforcer import PermissionEnforcer
from src.db.models.user import User


async def get_enforcer(session: DbSession) -> PermissionEnforcer:
    """Get permission enforcer dependency."""
    return PermissionEnforcer(session)


Enforcer = Annotated[PermissionEnforcer, Depends(get_enforcer)]


def require_permission(permission: str) -> Callable:
    """
    Dependency factory for single permission checks.
    
    Usage:
        @router.post("/products")
        async def create_product(
            user = Depends(get_current_user),
            _perm = Depends(require_permission("products:create")),
        ):
            ...
    """
    async def check_permission(
        request: Request,
        user: User = Depends(get_current_user),
        enforcer: PermissionEnforcer = Depends(get_enforcer),
    ) -> None:
        if not await enforcer.can(user, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
    return check_permission


def require_any_permission(*permissions: str) -> Callable:
    """
    Dependency factory for multiple permission checks (OR logic).
    
    Returns success if user has ANY of the specified permissions.
    
    Usage:
        @router.delete("/products/{id}")
        async def delete_product(
            user = Depends(get_current_user),
            _perm = Depends(require_any_permission("products:delete", "products:admin")),
        ):
            ...
    """
    async def check_permissions(
        request: Request,
        user: User = Depends(get_current_user),
        enforcer: PermissionEnforcer = Depends(get_enforcer),
    ) -> None:
        for permission in permissions:
            if await enforcer.can(user, permission):
                return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: one of {permissions} required",
        )
    return check_permissions
