# packages/api/src/services/audit.py
"""Audit logging service."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.audit_log import AuditLog, AuditAction
from src.db.models.user import User


class AuditService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _log(
        self,
        user: User,
        action: AuditAction,
        resource_type: str | None = None,
        resource_id: UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditLog:
        log = AuditLog(
            tenant_id=user.tenant_id,
            user_id=user.id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(log)
        await self.session.flush()
        return log

    async def log_login(self, user: User, ip_address: str | None = None, user_agent: str | None = None):
        await self._log(user, AuditAction.LOGIN, ip_address=ip_address, user_agent=user_agent)

    async def log_logout(self, user: User):
        await self._log(user, AuditAction.LOGOUT)

    async def log_permission_denied(
        self,
        user: User,
        permission: str,
        resource_type: str | None = None,
        ip_address: str | None = None,
    ):
        await self._log(
            user,
            AuditAction.PERMISSION_DENIED,
            resource_type=resource_type,
            details={"permission": permission},
            ip_address=ip_address,
        )

    async def log_resource_change(
        self,
        user: User,
        action: AuditAction,
        resource_type: str,
        resource_id: UUID,
        details: dict[str, Any] | None = None,
    ):
        await self._log(user, action, resource_type=resource_type, resource_id=resource_id, details=details)

    async def log_role_change(
        self,
        user: User,
        action: AuditAction,
        role_id: UUID,
        details: dict[str, Any] | None = None,
    ):
        await self._log(user, action, resource_type="role", resource_id=role_id, details=details)

    async def log_user_change(
        self,
        user: User,
        action: AuditAction,
        target_user_id: UUID,
        details: dict[str, Any] | None = None,
    ):
        await self._log(user, action, resource_type="user", resource_id=target_user_id, details=details)
