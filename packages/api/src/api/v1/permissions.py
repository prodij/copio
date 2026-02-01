# packages/api/src/api/v1/permissions.py
"""Permissions API endpoints."""

from typing import List

from fastapi import APIRouter, Depends

from src.api.deps import get_current_user_with_dev_bypass
from src.auth.dependencies import get_enforcer
from src.auth.enforcer import PermissionEnforcer
from src.auth.permissions import ALL_PERMISSIONS, RESOURCE_ACTIONS
from src.db.models.user import User

router = APIRouter(tags=["Permissions"])


@router.get("", response_model=List[str])
async def list_permissions():
    """List all available permissions in the system."""
    return ALL_PERMISSIONS


@router.get("/by-resource")
async def list_permissions_by_resource():
    """List permissions grouped by resource."""
    return RESOURCE_ACTIONS


@router.get("/me", response_model=List[str])
async def get_my_permissions(
    user: User = Depends(get_current_user_with_dev_bypass),
    enforcer: PermissionEnforcer = Depends(get_enforcer),
):
    """Get current user's effective permissions."""
    return await enforcer.get_permissions(user)
