"""Permission enforcement service."""

from typing import List, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.permissions import permission_matches, ALL_PERMISSIONS
from src.db.models.user import User
from src.db.models.user_role import UserRole
from src.db.models.role import Role


class PermissionEnforcer:
    """Enforces RBAC permissions for users."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache: dict[UUID, Set[str]] = {}

    async def _load_permissions(self, user: User) -> Set[str]:
        """Load user's permissions from their roles."""
        if user.id in self._cache:
            return self._cache[user.id]

        result = await self.session.execute(
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user.id)
            .where(Role.tenant_id == user.tenant_id)
        )
        roles = result.scalars().all()

        permissions: Set[str] = set()
        for role in roles:
            permissions.update(role.permissions)

        self._cache[user.id] = permissions
        return permissions

    async def can(self, user: User, permission: str) -> bool:
        """Check if user has a specific permission."""
        # Superusers bypass all permission checks
        if user.is_superuser:
            return True
        
        granted_permissions = await self._load_permissions(user)
        for granted in granted_permissions:
            if permission_matches(granted, permission):
                return True
        return False

    async def get_permissions(self, user: User) -> List[str]:
        """Get all effective permissions for a user."""
        granted_permissions = await self._load_permissions(user)
        effective: Set[str] = set()
        for granted in granted_permissions:
            if granted == "*:*":
                return ALL_PERMISSIONS
            elif "*" in granted:
                for perm in ALL_PERMISSIONS:
                    if permission_matches(granted, perm):
                        effective.add(perm)
            else:
                effective.add(granted)
        return sorted(effective)

    def clear_cache(self, user_id: UUID | None = None):
        """Clear the permissions cache."""
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()
