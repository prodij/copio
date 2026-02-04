# God-Mode Phase 1: Admin Audit Log + Tenant Management

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the foundation for God-mode with admin audit logging and tenant list/detail/actions.

**Architecture:**
- New `AdminAuditLog` model tracks all superuser actions with before/after diffs
- Admin endpoints under `/api/v1/admin/` require `is_superuser=True`
- Tenant status field enables suspend/reactivate workflow
- All mutating admin actions automatically logged via decorator

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 async, PostgreSQL, Alembic, pytest

---

## Task 1: AdminAuditLog Model

**Files:**
- Create: `packages/api/src/db/models/admin_audit_log.py`
- Modify: `packages/api/src/db/models/__init__.py`
- Test: `packages/api/tests/db/test_admin_audit_log_model.py`

**Step 1: Write the failing test**

Create `packages/api/tests/db/test_admin_audit_log_model.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/db/test_admin_audit_log_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.db.models.admin_audit_log'`

**Step 3: Write the model**

Create `packages/api/src/db/models/admin_audit_log.py`:

```python
"""Admin audit log model for tracking superuser actions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, generate_uuid


class AdminAuditLog(Base):
    """Append-only audit log for superuser/admin actions.

    Tracks all God-mode operations with before/after state diffs.
    Separate from tenant-scoped AuditLog for security isolation.
    """

    __tablename__ = "admin_audit_log"
    __table_args__ = (
        Index("idx_admin_audit_log_admin", "admin_id", "created_at"),
        Index("idx_admin_audit_log_action", "action", "created_at"),
        Index("idx_admin_audit_log_target", "target_type", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )

    # Who performed the action (must be superuser)
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # What action was performed
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # What was affected
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)

    # State diff
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Request context
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Impersonation context (if admin was impersonating a user)
    impersonating_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    # Relationships
    admin = relationship("User", foreign_keys=[admin_id], lazy="selectin")
    impersonating_user = relationship(
        "User", foreign_keys=[impersonating_user_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AdminAuditLog {self.action} by {self.admin_id}>"
```

**Step 4: Export from models package**

Modify `packages/api/src/db/models/__init__.py`, add these lines:

After line 38 (`from src.db.models.api_key import ApiKey`), add:
```python
from src.db.models.admin_audit_log import AdminAuditLog
```

In `__all__` list, after `"ApiKey",`, add:
```python
    "AdminAuditLog",
```

**Step 5: Run test to verify it passes**

Run: `cd packages/api && pytest tests/db/test_admin_audit_log_model.py -v`
Expected: PASS (3 tests)

**Step 6: Commit**

```bash
git add packages/api/src/db/models/admin_audit_log.py packages/api/src/db/models/__init__.py packages/api/tests/db/test_admin_audit_log_model.py
git commit -m "feat(api): add AdminAuditLog model for god-mode tracking"
```

---

## Task 2: AdminAuditLog Migration

**Files:**
- Create: `packages/api/alembic/versions/XXXX_add_admin_audit_log_table.py`

**Step 1: Generate migration**

Run: `cd packages/api && alembic revision --autogenerate -m "add_admin_audit_log_table"`

**Step 2: Review and adjust migration**

The generated migration should look like:

```python
"""add_admin_audit_log_table

Revision ID: <generated>
Revises: aa241d974370
Create Date: <generated>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = '<generated>'
down_revision: Union[str, None] = 'aa241d974370'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_label', sa.String(length=255), nullable=False),
        sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('impersonating_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['impersonating_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_admin_audit_log_action', 'admin_audit_log', ['action', 'created_at'], unique=False)
    op.create_index('idx_admin_audit_log_admin', 'admin_audit_log', ['admin_id', 'created_at'], unique=False)
    op.create_index('idx_admin_audit_log_target', 'admin_audit_log', ['target_type', 'target_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_admin_audit_log_target', table_name='admin_audit_log')
    op.drop_index('idx_admin_audit_log_admin', table_name='admin_audit_log')
    op.drop_index('idx_admin_audit_log_action', table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
```

**Step 3: Apply migration**

Run: `cd packages/api && alembic upgrade head`
Expected: Migration applies successfully

**Step 4: Verify table exists**

Run: `cd packages/api && alembic current`
Expected: Shows new revision as current

**Step 5: Commit**

```bash
git add packages/api/alembic/versions/*_add_admin_audit_log_table.py
git commit -m "feat(api): add admin_audit_log table migration"
```

---

## Task 3: Tenant Status Field

**Files:**
- Modify: `packages/api/src/db/models/tenant.py`
- Create: `packages/api/alembic/versions/XXXX_add_tenant_status.py`
- Test: `packages/api/tests/db/test_tenant_status.py`

**Step 1: Write the failing test**

Create `packages/api/tests/db/test_tenant_status.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/db/test_tenant_status.py -v`
Expected: FAIL with `TypeError` (no status field)

**Step 3: Add status fields to Tenant model**

Modify `packages/api/src/db/models/tenant.py`, add after line 56 (`onboarding_complete`):

```python
    # Status management
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
```

Add to imports at top:
```python
from datetime import datetime
from sqlalchemy import DateTime
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/db/test_tenant_status.py -v`
Expected: PASS (3 tests)

**Step 5: Generate and apply migration**

Run: `cd packages/api && alembic revision --autogenerate -m "add_tenant_status_fields"`

Review migration, then:
Run: `cd packages/api && alembic upgrade head`

**Step 6: Commit**

```bash
git add packages/api/src/db/models/tenant.py packages/api/alembic/versions/*_add_tenant_status_fields.py packages/api/tests/db/test_tenant_status.py
git commit -m "feat(api): add status fields to Tenant model"
```

---

## Task 4: Admin Audit Service

**Files:**
- Create: `packages/api/src/services/admin_audit.py`
- Test: `packages/api/tests/services/test_admin_audit.py`

**Step 1: Write the failing test**

Create `packages/api/tests/services/test_admin_audit.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/services/test_admin_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.services.admin_audit'`

**Step 3: Write the service**

Create `packages/api/src/services/admin_audit.py`:

```python
"""Admin audit logging service."""

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import User
from src.db.models.admin_audit_log import AdminAuditLog


async def log_action(
    session: AsyncSession,
    admin: User,
    action: str,
    target_type: str,
    target_label: str,
    ip_address: str,
    target_id: UUID | None = None,
    before_state: dict | None = None,
    after_state: dict | None = None,
    user_agent: str | None = None,
    impersonating_user_id: UUID | None = None,
) -> AdminAuditLog:
    """Log an admin action.

    Args:
        session: Database session
        admin: The superuser performing the action
        action: Action identifier (e.g., "tenant.suspend")
        target_type: Type of target (e.g., "tenant", "user")
        target_label: Human-readable target name
        ip_address: Request IP address
        target_id: Optional UUID of the target entity
        before_state: Optional state before the change
        after_state: Optional state after the change
        user_agent: Optional request user agent
        impersonating_user_id: Optional user being impersonated

    Returns:
        The created AdminAuditLog entry
    """
    log = AdminAuditLog(
        admin_id=admin.id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_label=target_label,
        before_state=before_state,
        after_state=after_state,
        ip_address=ip_address,
        user_agent=user_agent,
        impersonating_user_id=impersonating_user_id,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_logs_for_target(
    session: AsyncSession,
    target_type: str,
    target_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminAuditLog]:
    """Get audit logs for a specific target.

    Args:
        session: Database session
        target_type: Type of target
        target_id: UUID of the target
        limit: Maximum number of logs to return
        offset: Number of logs to skip

    Returns:
        List of AdminAuditLog entries
    """
    result = await session.execute(
        select(AdminAuditLog)
        .where(
            AdminAuditLog.target_type == target_type,
            AdminAuditLog.target_id == target_id,
        )
        .order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def get_logs(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    admin_id: UUID | None = None,
    action: str | None = None,
    target_type: str | None = None,
) -> tuple[list[AdminAuditLog], int]:
    """Get paginated audit logs with optional filters.

    Args:
        session: Database session
        limit: Maximum number of logs to return
        offset: Number of logs to skip
        admin_id: Optional filter by admin
        action: Optional filter by action
        target_type: Optional filter by target type

    Returns:
        Tuple of (logs, total_count)
    """
    query = select(AdminAuditLog)
    count_query = select(func.count(AdminAuditLog.id))

    if admin_id:
        query = query.where(AdminAuditLog.admin_id == admin_id)
        count_query = count_query.where(AdminAuditLog.admin_id == admin_id)

    if action:
        query = query.where(AdminAuditLog.action == action)
        count_query = count_query.where(AdminAuditLog.action == action)

    if target_type:
        query = query.where(AdminAuditLog.target_type == target_type)
        count_query = count_query.where(AdminAuditLog.target_type == target_type)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get paginated results
    result = await session.execute(
        query.order_by(AdminAuditLog.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    logs = list(result.scalars().all())

    return logs, total
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/services/test_admin_audit.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/api/src/services/admin_audit.py packages/api/tests/services/test_admin_audit.py
git commit -m "feat(api): add admin audit logging service"
```

---

## Task 5: Admin Tenants List Endpoint

**Files:**
- Modify: `packages/api/src/api/v1/admin.py`
- Test: `packages/api/tests/api/test_admin_tenants.py`

**Step 1: Write the failing test**

Create `packages/api/tests/api/test_admin_tenants.py`:

```python
"""Tests for admin tenants endpoints."""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant, User
from src.auth.tokens import create_access_token


def get_auth_headers(user: User) -> dict:
    """Get authorization headers for a user."""
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


class TestAdminTenantsEndpoints:
    """Tests for /admin/tenants endpoints."""

    async def test_list_tenants_requires_superuser(self, client: AsyncClient):
        """Test that listing tenants requires superuser."""
        response = await client.get("/api/v1/admin/tenants")
        assert response.status_code == 401

    async def test_list_tenants_forbidden_for_regular_user(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test regular users cannot list tenants."""
        client, session = client_with_db

        # Create tenant and regular user
        tenant = Tenant(id=uuid4(), name="Test", slug=f"test-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        user = User(
            id=uuid4(),
            email=f"user-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=False,
        )
        session.add(user)
        await session.commit()

        response = await client.get(
            "/api/v1/admin/tenants",
            headers=get_auth_headers(user),
        )
        assert response.status_code == 403

    async def test_list_tenants_success(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test superuser can list all tenants."""
        client, session = client_with_db

        # Create multiple tenants
        tenant1 = Tenant(id=uuid4(), name="Tenant A", slug=f"a-{uuid4().hex[:8]}")
        tenant2 = Tenant(id=uuid4(), name="Tenant B", slug=f"b-{uuid4().hex[:8]}")
        session.add_all([tenant1, tenant2])
        await session.commit()

        # Create superuser
        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant1.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.get(
            "/api/v1/admin/tenants",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 2
        assert "total" in data

    async def test_list_tenants_with_filters(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test filtering tenants by status."""
        client, session = client_with_db

        tenant1 = Tenant(
            id=uuid4(), name="Active Tenant", slug=f"active-{uuid4().hex[:8]}", status="active"
        )
        tenant2 = Tenant(
            id=uuid4(), name="Suspended Tenant", slug=f"susp-{uuid4().hex[:8]}", status="suspended"
        )
        session.add_all([tenant1, tenant2])
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant1.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.get(
            "/api/v1/admin/tenants?status=suspended",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["status"] == "suspended"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Implement the endpoints**

Modify `packages/api/src/api/v1/admin.py`, add after the existing imports:

```python
from sqlalchemy import func, select

from src.db.models import Tenant
```

Add new schemas after `SystemSettingUpdate`:

```python
class TenantListItem(BaseModel):
    """Schema for tenant list item."""

    id: UUID
    name: str
    slug: str
    status: str
    company_name: str | None
    timezone: str
    base_currency: str
    onboarding_complete: bool
    created_at: datetime
    updated_at: datetime
    user_count: int = 0

    class Config:
        from_attributes = True


class TenantListResponse(BaseModel):
    """Schema for paginated tenant list."""

    items: list[TenantListItem]
    total: int
    limit: int
    offset: int
```

Add new endpoints after the existing settings endpoints:

```python
# =============================================================================
# TENANT MANAGEMENT
# =============================================================================


@router.get("/tenants", response_model=TenantListResponse)
async def list_tenants(
    session: DbSession,
    _user: User = Depends(require_superuser),
    status: str | None = None,
    search: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List all tenants with optional filters. Requires superuser."""
    from src.db.models import User as UserModel

    # Build query
    query = select(Tenant)
    count_query = select(func.count(Tenant.id))

    if status:
        query = query.where(Tenant.status == status)
        count_query = count_query.where(Tenant.status == status)

    if search:
        search_filter = Tenant.name.ilike(f"%{search}%") | Tenant.slug.ilike(f"%{search}%")
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    # Exclude soft-deleted
    query = query.where(Tenant.deleted_at.is_(None))
    count_query = count_query.where(Tenant.deleted_at.is_(None))

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get tenants
    result = await session.execute(
        query.order_by(Tenant.created_at.desc()).limit(limit).offset(offset)
    )
    tenants = result.scalars().all()

    # Get user counts per tenant
    user_counts_result = await session.execute(
        select(UserModel.tenant_id, func.count(UserModel.id))
        .where(UserModel.is_active == True)
        .group_by(UserModel.tenant_id)
    )
    user_counts = {row[0]: row[1] for row in user_counts_result.all()}

    items = []
    for tenant in tenants:
        item = TenantListItem(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            company_name=tenant.company_name,
            timezone=tenant.timezone,
            base_currency=tenant.base_currency,
            onboarding_complete=tenant.onboarding_complete,
            created_at=tenant.created_at,
            updated_at=tenant.updated_at,
            user_count=user_counts.get(tenant.id, 0),
        )
        items.append(item)

    return TenantListResponse(items=items, total=total, limit=limit, offset=offset)
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add packages/api/src/api/v1/admin.py packages/api/tests/api/test_admin_tenants.py
git commit -m "feat(api): add admin tenants list endpoint"
```

---

## Task 6: Admin Tenant Detail Endpoint

**Files:**
- Modify: `packages/api/src/api/v1/admin.py`
- Modify: `packages/api/tests/api/test_admin_tenants.py`

**Step 1: Write the failing test**

Add to `packages/api/tests/api/test_admin_tenants.py`:

```python
class TestAdminTenantDetailEndpoint:
    """Tests for /admin/tenants/:id endpoint."""

    async def test_get_tenant_detail(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test superuser can get tenant details."""
        client, session = client_with_db

        tenant = Tenant(
            id=uuid4(),
            name="Detail Test",
            slug=f"detail-{uuid4().hex[:8]}",
            company_name="Detail Corp",
            timezone="America/New_York",
        )
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.get(
            f"/api/v1/admin/tenants/{tenant.id}",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(tenant.id)
        assert data["name"] == "Detail Test"
        assert data["company_name"] == "Detail Corp"

    async def test_get_tenant_not_found(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test 404 for non-existent tenant."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="Admin Tenant", slug=f"admin-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.get(
            f"/api/v1/admin/tenants/{uuid4()}",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py::TestAdminTenantDetailEndpoint -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Add the endpoint**

Add schema to `packages/api/src/api/v1/admin.py`:

```python
class TenantDetailResponse(BaseModel):
    """Schema for tenant detail."""

    id: UUID
    name: str
    slug: str
    status: str
    timezone: str
    base_currency: str
    settings: dict
    company_name: str | None
    legal_name: str | None
    tax_id: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    phone: str | None
    email: str | None
    website: str | None
    logo_url: str | None
    onboarding_complete: bool
    suspended_at: datetime | None
    suspended_reason: str | None
    created_at: datetime
    updated_at: datetime
    user_count: int = 0

    class Config:
        from_attributes = True
```

Add endpoint:

```python
@router.get("/tenants/{tenant_id}", response_model=TenantDetailResponse)
async def get_tenant(
    tenant_id: UUID,
    session: DbSession,
    _user: User = Depends(require_superuser),
):
    """Get tenant details. Requires superuser."""
    from src.db.models import User as UserModel

    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Get user count
    user_count_result = await session.execute(
        select(func.count(UserModel.id)).where(
            UserModel.tenant_id == tenant_id,
            UserModel.is_active == True,
        )
    )
    user_count = user_count_result.scalar() or 0

    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        timezone=tenant.timezone,
        base_currency=tenant.base_currency,
        settings=tenant.settings,
        company_name=tenant.company_name,
        legal_name=tenant.legal_name,
        tax_id=tenant.tax_id,
        address_line1=tenant.address_line1,
        address_line2=tenant.address_line2,
        city=tenant.city,
        state=tenant.state,
        postal_code=tenant.postal_code,
        country=tenant.country,
        phone=tenant.phone,
        email=tenant.email,
        website=tenant.website,
        logo_url=tenant.logo_url,
        onboarding_complete=tenant.onboarding_complete,
        suspended_at=tenant.suspended_at,
        suspended_reason=tenant.suspended_reason,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        user_count=user_count,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py::TestAdminTenantDetailEndpoint -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add packages/api/src/api/v1/admin.py packages/api/tests/api/test_admin_tenants.py
git commit -m "feat(api): add admin tenant detail endpoint"
```

---

## Task 7: Suspend/Reactivate Tenant Endpoints

**Files:**
- Modify: `packages/api/src/api/v1/admin.py`
- Modify: `packages/api/tests/api/test_admin_tenants.py`

**Step 1: Write the failing tests**

Add to `packages/api/tests/api/test_admin_tenants.py`:

```python
class TestAdminTenantActions:
    """Tests for tenant action endpoints."""

    async def test_suspend_tenant(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test suspending a tenant."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="To Suspend", slug=f"suspend-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.post(
            f"/api/v1/admin/tenants/{tenant.id}/suspend",
            headers=get_auth_headers(admin),
            json={"reason": "Non-payment"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "suspended"
        assert data["suspended_reason"] == "Non-payment"
        assert data["suspended_at"] is not None

    async def test_reactivate_tenant(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test reactivating a suspended tenant."""
        client, session = client_with_db
        from datetime import datetime, timezone

        tenant = Tenant(
            id=uuid4(),
            name="To Reactivate",
            slug=f"react-{uuid4().hex[:8]}",
            status="suspended",
            suspended_at=datetime.now(timezone.utc),
            suspended_reason="Testing",
        )
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        response = await client.post(
            f"/api/v1/admin/tenants/{tenant.id}/reactivate",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["suspended_at"] is None
        assert data["suspended_reason"] is None

    async def test_suspend_logs_audit(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test that suspending a tenant creates an audit log."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="Audit Test", slug=f"audit-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        await client.post(
            f"/api/v1/admin/tenants/{tenant.id}/suspend",
            headers=get_auth_headers(admin),
            json={"reason": "Audit test"},
        )

        # Check audit log was created
        from sqlalchemy import select
        from src.db.models.admin_audit_log import AdminAuditLog

        result = await session.execute(
            select(AdminAuditLog).where(
                AdminAuditLog.action == "tenant.suspend",
                AdminAuditLog.target_id == tenant.id,
            )
        )
        log = result.scalar_one_or_none()
        assert log is not None
        assert log.admin_id == admin.id
        assert log.before_state["status"] == "active"
        assert log.after_state["status"] == "suspended"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py::TestAdminTenantActions -v`
Expected: FAIL with 404/405 (endpoints don't exist)

**Step 3: Add schemas and endpoints**

Add to `packages/api/src/api/v1/admin.py`:

```python
class SuspendTenantRequest(BaseModel):
    """Request schema for suspending a tenant."""

    reason: str | None = None
```

Add endpoints (include Request import at top):

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
```

```python
@router.post("/tenants/{tenant_id}/suspend", response_model=TenantDetailResponse)
async def suspend_tenant(
    tenant_id: UUID,
    request: Request,
    data: SuspendTenantRequest,
    session: DbSession,
    user: User = Depends(require_superuser),
):
    """Suspend a tenant. Requires superuser."""
    from datetime import datetime, timezone
    from src.services import admin_audit

    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.status == "suspended":
        raise HTTPException(status_code=400, detail="Tenant is already suspended")

    # Capture before state
    before_state = {"status": tenant.status, "suspended_at": None, "suspended_reason": None}

    # Update tenant
    tenant.status = "suspended"
    tenant.suspended_at = datetime.now(timezone.utc)
    tenant.suspended_reason = data.reason

    after_state = {
        "status": "suspended",
        "suspended_at": tenant.suspended_at.isoformat(),
        "suspended_reason": data.reason,
    }

    await session.commit()
    await session.refresh(tenant)

    # Log the action
    await admin_audit.log_action(
        session=session,
        admin=user,
        action="tenant.suspend",
        target_type="tenant",
        target_id=tenant.id,
        target_label=tenant.name,
        before_state=before_state,
        after_state=after_state,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
    )

    # Get user count for response
    from src.db.models import User as UserModel

    user_count_result = await session.execute(
        select(func.count(UserModel.id)).where(
            UserModel.tenant_id == tenant_id,
            UserModel.is_active == True,
        )
    )
    user_count = user_count_result.scalar() or 0

    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        timezone=tenant.timezone,
        base_currency=tenant.base_currency,
        settings=tenant.settings,
        company_name=tenant.company_name,
        legal_name=tenant.legal_name,
        tax_id=tenant.tax_id,
        address_line1=tenant.address_line1,
        address_line2=tenant.address_line2,
        city=tenant.city,
        state=tenant.state,
        postal_code=tenant.postal_code,
        country=tenant.country,
        phone=tenant.phone,
        email=tenant.email,
        website=tenant.website,
        logo_url=tenant.logo_url,
        onboarding_complete=tenant.onboarding_complete,
        suspended_at=tenant.suspended_at,
        suspended_reason=tenant.suspended_reason,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        user_count=user_count,
    )


@router.post("/tenants/{tenant_id}/reactivate", response_model=TenantDetailResponse)
async def reactivate_tenant(
    tenant_id: UUID,
    request: Request,
    session: DbSession,
    user: User = Depends(require_superuser),
):
    """Reactivate a suspended tenant. Requires superuser."""
    from src.services import admin_audit

    result = await session.execute(
        select(Tenant).where(Tenant.id == tenant_id, Tenant.deleted_at.is_(None))
    )
    tenant = result.scalar_one_or_none()

    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if tenant.status != "suspended":
        raise HTTPException(status_code=400, detail="Tenant is not suspended")

    # Capture before state
    before_state = {
        "status": tenant.status,
        "suspended_at": tenant.suspended_at.isoformat() if tenant.suspended_at else None,
        "suspended_reason": tenant.suspended_reason,
    }

    # Update tenant
    tenant.status = "active"
    tenant.suspended_at = None
    tenant.suspended_reason = None

    after_state = {"status": "active", "suspended_at": None, "suspended_reason": None}

    await session.commit()
    await session.refresh(tenant)

    # Log the action
    await admin_audit.log_action(
        session=session,
        admin=user,
        action="tenant.reactivate",
        target_type="tenant",
        target_id=tenant.id,
        target_label=tenant.name,
        before_state=before_state,
        after_state=after_state,
        ip_address=request.client.host if request.client else "unknown",
        user_agent=request.headers.get("user-agent"),
    )

    # Get user count for response
    from src.db.models import User as UserModel

    user_count_result = await session.execute(
        select(func.count(UserModel.id)).where(
            UserModel.tenant_id == tenant_id,
            UserModel.is_active == True,
        )
    )
    user_count = user_count_result.scalar() or 0

    return TenantDetailResponse(
        id=tenant.id,
        name=tenant.name,
        slug=tenant.slug,
        status=tenant.status,
        timezone=tenant.timezone,
        base_currency=tenant.base_currency,
        settings=tenant.settings,
        company_name=tenant.company_name,
        legal_name=tenant.legal_name,
        tax_id=tenant.tax_id,
        address_line1=tenant.address_line1,
        address_line2=tenant.address_line2,
        city=tenant.city,
        state=tenant.state,
        postal_code=tenant.postal_code,
        country=tenant.country,
        phone=tenant.phone,
        email=tenant.email,
        website=tenant.website,
        logo_url=tenant.logo_url,
        onboarding_complete=tenant.onboarding_complete,
        suspended_at=tenant.suspended_at,
        suspended_reason=tenant.suspended_reason,
        created_at=tenant.created_at,
        updated_at=tenant.updated_at,
        user_count=user_count,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/api/test_admin_tenants.py::TestAdminTenantActions -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add packages/api/src/api/v1/admin.py packages/api/tests/api/test_admin_tenants.py
git commit -m "feat(api): add suspend/reactivate tenant endpoints with audit logging"
```

---

## Task 8: Admin Audit Log Endpoint

**Files:**
- Modify: `packages/api/src/api/v1/admin.py`
- Create: `packages/api/tests/api/test_admin_audit.py`

**Step 1: Write the failing test**

Create `packages/api/tests/api/test_admin_audit.py`:

```python
"""Tests for admin audit log endpoint."""

import pytest
from uuid import uuid4
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import Tenant, User
from src.db.models.admin_audit_log import AdminAuditLog
from src.auth.tokens import create_access_token


def get_auth_headers(user: User) -> dict:
    """Get authorization headers for a user."""
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


class TestAdminAuditEndpoint:
    """Tests for /admin/audit endpoint."""

    async def test_list_audit_logs(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test superuser can list audit logs."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="Audit Tenant", slug=f"audit-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        # Create some audit logs
        for i in range(3):
            log = AdminAuditLog(
                admin_id=admin.id,
                action=f"test.action{i}",
                target_type="test",
                target_id=uuid4(),
                target_label=f"Test {i}",
                ip_address="127.0.0.1",
            )
            session.add(log)
        await session.commit()

        response = await client.get(
            "/api/v1/admin/audit",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) >= 3
        assert "total" in data

    async def test_filter_audit_logs_by_action(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test filtering audit logs by action."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="Filter Tenant", slug=f"filter-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        # Create logs with different actions
        log1 = AdminAuditLog(
            admin_id=admin.id,
            action="tenant.suspend",
            target_type="tenant",
            target_label="Tenant A",
            ip_address="127.0.0.1",
        )
        log2 = AdminAuditLog(
            admin_id=admin.id,
            action="user.update",
            target_type="user",
            target_label="User B",
            ip_address="127.0.0.1",
        )
        session.add_all([log1, log2])
        await session.commit()

        response = await client.get(
            "/api/v1/admin/audit?action=tenant.suspend",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["items"]:
            assert item["action"] == "tenant.suspend"

    async def test_get_audit_log_detail(
        self, client_with_db: tuple[AsyncClient, AsyncSession]
    ):
        """Test getting single audit log detail."""
        client, session = client_with_db

        tenant = Tenant(id=uuid4(), name="Detail Tenant", slug=f"detail-{uuid4().hex[:8]}")
        session.add(tenant)
        await session.commit()

        admin = User(
            id=uuid4(),
            email=f"admin-{uuid4().hex[:8]}@test.com",
            hashed_password="hash",
            tenant_id=tenant.id,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(admin)
        await session.commit()

        log = AdminAuditLog(
            admin_id=admin.id,
            action="tenant.update",
            target_type="tenant",
            target_id=tenant.id,
            target_label=tenant.name,
            before_state={"name": "Old Name"},
            after_state={"name": "New Name"},
            ip_address="192.168.1.1",
            user_agent="Test/1.0",
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)

        response = await client.get(
            f"/api/v1/admin/audit/{log.id}",
            headers=get_auth_headers(admin),
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(log.id)
        assert data["action"] == "tenant.update"
        assert data["before_state"]["name"] == "Old Name"
        assert data["after_state"]["name"] == "New Name"
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && pytest tests/api/test_admin_audit.py -v`
Expected: FAIL with 404 (endpoint doesn't exist)

**Step 3: Add schemas and endpoints**

Add to `packages/api/src/api/v1/admin.py`:

```python
class AdminAuditLogItem(BaseModel):
    """Schema for audit log list item."""

    id: UUID
    admin_id: UUID
    admin_email: str | None = None
    action: str
    target_type: str
    target_id: UUID | None
    target_label: str
    ip_address: str
    created_at: datetime

    class Config:
        from_attributes = True


class AdminAuditLogDetail(BaseModel):
    """Schema for audit log detail."""

    id: UUID
    admin_id: UUID
    admin_email: str | None = None
    action: str
    target_type: str
    target_id: UUID | None
    target_label: str
    before_state: dict | None
    after_state: dict | None
    ip_address: str
    user_agent: str | None
    impersonating_user_id: UUID | None
    impersonating_user_email: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminAuditLogListResponse(BaseModel):
    """Schema for paginated audit log list."""

    items: list[AdminAuditLogItem]
    total: int
    limit: int
    offset: int
```

Add endpoints:

```python
# =============================================================================
# AUDIT LOG
# =============================================================================


@router.get("/audit", response_model=AdminAuditLogListResponse)
async def list_audit_logs(
    session: DbSession,
    _user: User = Depends(require_superuser),
    action: str | None = None,
    target_type: str | None = None,
    admin_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
):
    """List admin audit logs with optional filters. Requires superuser."""
    from src.db.models.admin_audit_log import AdminAuditLog
    from src.db.models import User as UserModel

    query = select(AdminAuditLog)
    count_query = select(func.count(AdminAuditLog.id))

    if action:
        query = query.where(AdminAuditLog.action == action)
        count_query = count_query.where(AdminAuditLog.action == action)

    if target_type:
        query = query.where(AdminAuditLog.target_type == target_type)
        count_query = count_query.where(AdminAuditLog.target_type == target_type)

    if admin_id:
        query = query.where(AdminAuditLog.admin_id == admin_id)
        count_query = count_query.where(AdminAuditLog.admin_id == admin_id)

    # Get total count
    total_result = await session.execute(count_query)
    total = total_result.scalar() or 0

    # Get logs
    result = await session.execute(
        query.order_by(AdminAuditLog.created_at.desc()).limit(limit).offset(offset)
    )
    logs = result.scalars().all()

    # Get admin emails
    admin_ids = {log.admin_id for log in logs}
    if admin_ids:
        admin_result = await session.execute(
            select(UserModel.id, UserModel.email).where(UserModel.id.in_(admin_ids))
        )
        admin_emails = {row[0]: row[1] for row in admin_result.all()}
    else:
        admin_emails = {}

    items = [
        AdminAuditLogItem(
            id=log.id,
            admin_id=log.admin_id,
            admin_email=admin_emails.get(log.admin_id),
            action=log.action,
            target_type=log.target_type,
            target_id=log.target_id,
            target_label=log.target_label,
            ip_address=str(log.ip_address),
            created_at=log.created_at,
        )
        for log in logs
    ]

    return AdminAuditLogListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/audit/{log_id}", response_model=AdminAuditLogDetail)
async def get_audit_log(
    log_id: UUID,
    session: DbSession,
    _user: User = Depends(require_superuser),
):
    """Get audit log detail. Requires superuser."""
    from src.db.models.admin_audit_log import AdminAuditLog
    from src.db.models import User as UserModel

    result = await session.execute(
        select(AdminAuditLog).where(AdminAuditLog.id == log_id)
    )
    log = result.scalar_one_or_none()

    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")

    # Get admin email
    admin_result = await session.execute(
        select(UserModel.email).where(UserModel.id == log.admin_id)
    )
    admin_email = admin_result.scalar_one_or_none()

    # Get impersonating user email if applicable
    impersonating_email = None
    if log.impersonating_user_id:
        imp_result = await session.execute(
            select(UserModel.email).where(UserModel.id == log.impersonating_user_id)
        )
        impersonating_email = imp_result.scalar_one_or_none()

    return AdminAuditLogDetail(
        id=log.id,
        admin_id=log.admin_id,
        admin_email=admin_email,
        action=log.action,
        target_type=log.target_type,
        target_id=log.target_id,
        target_label=log.target_label,
        before_state=log.before_state,
        after_state=log.after_state,
        ip_address=str(log.ip_address),
        user_agent=log.user_agent,
        impersonating_user_id=log.impersonating_user_id,
        impersonating_user_email=impersonating_email,
        created_at=log.created_at,
    )
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && pytest tests/api/test_admin_audit.py -v`
Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add packages/api/src/api/v1/admin.py packages/api/tests/api/test_admin_audit.py
git commit -m "feat(api): add admin audit log endpoints"
```

---

## Task 9: Run Full Test Suite

**Step 1: Run all tests**

Run: `cd packages/api && pytest -v`
Expected: All tests pass

**Step 2: Run type checking**

Run: `cd packages/api && mypy src`
Expected: No errors

**Step 3: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address any issues from full test suite"
```

---

## Summary

Phase 1 delivers:

1. **AdminAuditLog model** - Tracks all admin actions with diffs
2. **Tenant status fields** - status, suspended_at, suspended_reason, deleted_at
3. **Admin audit service** - log_action(), get_logs(), get_logs_for_target()
4. **Tenant list endpoint** - GET /api/v1/admin/tenants with filters
5. **Tenant detail endpoint** - GET /api/v1/admin/tenants/:id
6. **Suspend/reactivate endpoints** - POST with automatic audit logging
7. **Audit log endpoints** - GET /api/v1/admin/audit with filters

All endpoints require superuser access and all mutating actions are audit logged.
