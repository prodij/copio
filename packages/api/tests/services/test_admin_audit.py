"""Tests for admin audit service."""

import pytest
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant, User
from src.db.models.admin_audit_log import AdminAuditLog
from src.services import admin_audit


class TestAdminAuditService:
    """Tests for admin audit logging service."""

    async def test_log_admin_action(
        self, db_session: AsyncSession, admin_user: User, test_tenant: Tenant
    ):
        """Test logging an admin action."""
        await admin_audit.log_action(
            session=db_session,
            admin=admin_user,
            action="tenant.view",
            target_type="tenant",
            target_id=test_tenant.id,
            target_label=test_tenant.name,
            ip_address="192.168.1.1",
        )

        result = await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.admin_id == admin_user.id)
        )
        log = result.scalar_one()

        assert log.action == "tenant.view"
        assert log.target_type == "tenant"
        assert log.target_id == test_tenant.id

    async def test_log_admin_action_with_diff(
        self, db_session: AsyncSession, admin_user: User, test_tenant: Tenant
    ):
        """Test logging an action with before/after state."""
        before = {"status": "active"}
        after = {"status": "suspended"}

        await admin_audit.log_action(
            session=db_session,
            admin=admin_user,
            action="tenant.suspend",
            target_type="tenant",
            target_id=test_tenant.id,
            target_label=test_tenant.name,
            before_state=before,
            after_state=after,
            ip_address="10.0.0.1",
            user_agent="Admin/1.0",
        )

        result = await db_session.execute(
            select(AdminAuditLog).where(AdminAuditLog.action == "tenant.suspend")
        )
        log = result.scalar_one()

        assert log.before_state == before
        assert log.after_state == after
        assert log.user_agent == "Admin/1.0"

    async def test_get_audit_logs_for_target(
        self, db_session: AsyncSession, admin_user: User, test_tenant: Tenant
    ):
        """Test retrieving audit logs for a specific target."""
        # Create multiple logs
        for i in range(3):
            await admin_audit.log_action(
                session=db_session,
                admin=admin_user,
                action=f"tenant.action{i}",
                target_type="tenant",
                target_id=test_tenant.id,
                target_label=test_tenant.name,
                ip_address="127.0.0.1",
            )

        logs = await admin_audit.get_logs_for_target(
            session=db_session,
            target_type="tenant",
            target_id=test_tenant.id,
        )

        assert len(logs) == 3

    async def test_get_audit_logs_paginated(
        self, db_session: AsyncSession, admin_user: User, test_tenant: Tenant
    ):
        """Test paginated audit log retrieval."""
        # Create 5 logs
        for i in range(5):
            await admin_audit.log_action(
                session=db_session,
                admin=admin_user,
                action=f"test.action{i}",
                target_type="test",
                target_id=uuid4(),
                target_label=f"Test {i}",
                ip_address="127.0.0.1",
            )

        logs, total = await admin_audit.get_logs(
            session=db_session,
            limit=2,
            offset=0,
        )

        assert len(logs) == 2
        assert total == 5
