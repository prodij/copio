"""Tests for AdminAuditLog model."""

import pytest
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant, User
from src.db.models.admin_audit_log import AdminAuditLog


class TestAdminAuditLogModel:
    """Tests for AdminAuditLog model."""

    async def test_create_admin_audit_log(
        self, db_session: AsyncSession, test_tenant: Tenant, admin_user: User
    ):
        """Test creating an admin audit log entry."""
        log = AdminAuditLog(
            admin_id=admin_user.id,
            action="tenant.update",
            target_type="tenant",
            target_id=test_tenant.id,
            target_label=test_tenant.name,
            before_state={"timezone": "America/Los_Angeles"},
            after_state={"timezone": "America/New_York"},
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.id is not None
        assert log.admin_id == admin_user.id
        assert log.action == "tenant.update"
        assert log.before_state["timezone"] == "America/Los_Angeles"
        assert log.after_state["timezone"] == "America/New_York"
        assert log.created_at is not None

    async def test_admin_audit_log_with_impersonation(
        self, db_session: AsyncSession, admin_user: User, test_user: User
    ):
        """Test audit log with impersonation context."""
        log = AdminAuditLog(
            admin_id=admin_user.id,
            action="order.view",
            target_type="order",
            target_id=uuid4(),
            target_label="Order #1234",
            impersonating_user_id=test_user.id,
            ip_address="10.0.0.1",
        )
        db_session.add(log)
        await db_session.commit()
        await db_session.refresh(log)

        assert log.impersonating_user_id == test_user.id

    async def test_admin_audit_log_nullable_fields(
        self, db_session: AsyncSession, admin_user: User
    ):
        """Test audit log with minimal required fields."""
        log = AdminAuditLog(
            admin_id=admin_user.id,
            action="setting.update",
            target_type="setting",
            target_label="email_verification",
            ip_address="127.0.0.1",
        )
        db_session.add(log)
        await db_session.commit()

        assert log.target_id is None
        assert log.before_state is None
        assert log.after_state is None
        assert log.impersonating_user_id is None
        assert log.user_agent is None
