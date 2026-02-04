"""Tests for Tenant status field."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant


class TestTenantStatus:
    """Tests for Tenant status field."""

    async def test_tenant_default_status_active(self, db_session: AsyncSession):
        """Test new tenants default to 'active' status."""
        tenant = Tenant(
            name="Status Test",
            slug="status-test",
        )
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        assert tenant.status == "active"

    async def test_tenant_can_be_suspended(self, db_session: AsyncSession):
        """Test tenant can be set to suspended."""
        tenant = Tenant(
            name="Suspend Test",
            slug="suspend-test",
            status="suspended",
        )
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        assert tenant.status == "suspended"

    async def test_tenant_suspended_at_tracked(self, db_session: AsyncSession):
        """Test suspended_at timestamp is recorded."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        tenant = Tenant(
            name="Suspend Time Test",
            slug="suspend-time-test",
            status="suspended",
            suspended_at=now,
            suspended_reason="Non-payment",
        )
        db_session.add(tenant)
        await db_session.commit()
        await db_session.refresh(tenant)

        assert tenant.suspended_at is not None
        assert tenant.suspended_reason == "Non-payment"
