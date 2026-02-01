# User Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement granular permission system with dynamic roles, invite-only user management, and audit logging for Copio ERP.

**Architecture:** Hybrid RBAC using Casbin for policy enforcement, fastapi-users for authentication, SQLAlchemy models for roles/permissions/audit. Frontend with Next.js App Router and shadcn/ui.

**Tech Stack:** Python/FastAPI, Casbin (async-casbin, casbin-sqlalchemy-adapter), SQLAlchemy, Next.js 14, shadcn/ui, TailwindCSS

---

## Task 1: Database Schema — Roles and User Roles

**Files:**
- Create: `packages/api/src/db/models/role.py`
- Create: `packages/api/src/db/models/user_role.py`
- Modify: `packages/api/src/db/models/__init__.py`
- Test: `packages/api/tests/db/test_role_models.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/db/test_role_models.py
import pytest
from uuid import uuid4
from sqlalchemy import select
from src.db.models.role import Role
from src.db.models.user_role import UserRole


@pytest.mark.asyncio
async def test_create_role(db_session, test_tenant):
    """Role can be created with permissions."""
    role = Role(
        tenant_id=test_tenant.id,
        name="Warehouse Staff",
        description="Inventory and receiving",
        permissions=["inventory:view", "inventory:adjust", "purchase_orders:receive"],
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)

    assert role.id is not None
    assert role.name == "Warehouse Staff"
    assert "inventory:view" in role.permissions
    assert role.is_system is False


@pytest.mark.asyncio
async def test_user_role_assignment(db_session, test_tenant, test_user):
    """User can be assigned to a role."""
    role = Role(
        tenant_id=test_tenant.id,
        name="Manager",
        permissions=["*:view", "products:edit"],
    )
    db_session.add(role)
    await db_session.commit()

    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()

    # Query back
    result = await db_session.execute(
        select(UserRole).where(UserRole.user_id == test_user.id)
    )
    assignments = result.scalars().all()
    assert len(assignments) == 1
    assert assignments[0].role_id == role.id


@pytest.mark.asyncio
async def test_role_unique_per_tenant(db_session, test_tenant):
    """Role names must be unique within a tenant."""
    role1 = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"])
    db_session.add(role1)
    await db_session.commit()

    role2 = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:view"])
    db_session.add(role2)
    
    with pytest.raises(Exception):  # IntegrityError
        await db_session.commit()
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/db/test_role_models.py -v`
Expected: FAIL with "No module named 'src.db.models.role'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/db/models/role.py
"""Role model for dynamic RBAC."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from src.db.models.tenant import Tenant
    from src.db.models.user_role import UserRole


class Role(Base, TimestampMixin):
    """Role with customizable permissions per tenant."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(default=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list)

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="roles")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
```

```python
# packages/api/src/db/models/user_role.py
"""User-Role assignment model."""

from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid


class UserRole(Base, TimestampMixin):
    """Maps users to roles."""

    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_roles"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Relationships
    user = relationship("User", back_populates="user_roles")
    role = relationship("Role", back_populates="user_roles")

    def __repr__(self) -> str:
        return f"<UserRole user={self.user_id} role={self.role_id}>"
```

**Step 4: Update model exports and relationships**

```python
# Add to packages/api/src/db/models/__init__.py
from src.db.models.role import Role
from src.db.models.user_role import UserRole
```

Update `packages/api/src/db/models/tenant.py` — add relationship:
```python
roles: Mapped[list["Role"]] = relationship("Role", back_populates="tenant")
```

Update `packages/api/src/db/models/user.py` — add relationship:
```python
user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user")
```

**Step 5: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/db/test_role_models.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/api/src/db/models/role.py packages/api/src/db/models/user_role.py
git add packages/api/src/db/models/__init__.py packages/api/src/db/models/tenant.py packages/api/src/db/models/user.py
git add packages/api/tests/db/test_role_models.py
git commit -m "feat(api): add Role and UserRole models for RBAC"
```

---

## Task 2: Database Schema — User Invites

**Files:**
- Create: `packages/api/src/db/models/user_invite.py`
- Modify: `packages/api/src/db/models/__init__.py`
- Test: `packages/api/tests/db/test_user_invite_model.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/db/test_user_invite_model.py
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import select
from src.db.models.user_invite import UserInvite


@pytest.mark.asyncio
async def test_create_invite(db_session, test_tenant, test_user, test_role):
    """Invite can be created with expiration."""
    invite = UserInvite(
        tenant_id=test_tenant.id,
        email="newuser@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db_session.add(invite)
    await db_session.commit()
    await db_session.refresh(invite)

    assert invite.id is not None
    assert invite.token is not None  # Auto-generated
    assert len(invite.token) == 64  # Secure token
    assert invite.accepted_at is None


@pytest.mark.asyncio
async def test_invite_is_valid(db_session, test_tenant, test_user, test_role):
    """Invite validity check works."""
    valid_invite = UserInvite(
        tenant_id=test_tenant.id,
        email="valid@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    expired_invite = UserInvite(
        tenant_id=test_tenant.id,
        email="expired@example.com",
        role_id=test_role.id,
        invited_by=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(days=1),
    )
    db_session.add_all([valid_invite, expired_invite])
    await db_session.commit()

    assert valid_invite.is_valid is True
    assert expired_invite.is_valid is False

    # Accept the valid invite
    valid_invite.accepted_at = datetime.now(timezone.utc)
    await db_session.commit()
    assert valid_invite.is_valid is False  # Already accepted
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/db/test_user_invite_model.py -v`
Expected: FAIL with "No module named 'src.db.models.user_invite'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/db/models/user_invite.py
"""User invite model for invite-only onboarding."""

import secrets
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from src.db.models.role import Role
    from src.db.models.tenant import Tenant
    from src.db.models.user import User


def generate_invite_token() -> str:
    """Generate a secure 64-char token."""
    return secrets.token_hex(32)


class UserInvite(Base, TimestampMixin):
    """Pending user invitation."""

    __tablename__ = "user_invites"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("roles.id"),
        nullable=False,
    )
    token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        default=generate_invite_token,
    )
    invited_by: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    accepted_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant")
    role: Mapped["Role"] = relationship("Role")
    inviter: Mapped["User"] = relationship("User", foreign_keys=[invited_by])

    @property
    def is_valid(self) -> bool:
        """Check if invite is still valid (not expired, not accepted)."""
        if self.accepted_at is not None:
            return False
        return datetime.now(timezone.utc) < self.expires_at

    def __repr__(self) -> str:
        return f"<UserInvite {self.email}>"
```

**Step 4: Update exports**

```python
# Add to packages/api/src/db/models/__init__.py
from src.db.models.user_invite import UserInvite
```

**Step 5: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/db/test_user_invite_model.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/api/src/db/models/user_invite.py packages/api/src/db/models/__init__.py
git add packages/api/tests/db/test_user_invite_model.py
git commit -m "feat(api): add UserInvite model for invite-only onboarding"
```

---

## Task 3: Database Schema — Audit Log

**Files:**
- Create: `packages/api/src/db/models/audit_log.py`
- Modify: `packages/api/src/db/models/__init__.py`
- Test: `packages/api/tests/db/test_audit_log_model.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/db/test_audit_log_model.py
import pytest
from sqlalchemy import select
from src.db.models.audit_log import AuditLog, AuditAction


@pytest.mark.asyncio
async def test_create_audit_log(db_session, test_tenant, test_user):
    """Audit log entry can be created."""
    entry = AuditLog(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        action=AuditAction.LOGIN,
        ip_address="192.168.1.1",
        user_agent="Mozilla/5.0",
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)

    assert entry.id is not None
    assert entry.action == AuditAction.LOGIN


@pytest.mark.asyncio
async def test_audit_log_with_resource(db_session, test_tenant, test_user):
    """Audit log can track resource changes."""
    from uuid import uuid4
    
    resource_id = uuid4()
    entry = AuditLog(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        action=AuditAction.RESOURCE_DELETED,
        resource_type="vendor",
        resource_id=resource_id,
        details={"vendor_name": "Old Supplier Inc"},
    )
    db_session.add(entry)
    await db_session.commit()

    result = await db_session.execute(
        select(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    log = result.scalar_one()
    assert log.details["vendor_name"] == "Old Supplier Inc"


@pytest.mark.asyncio
async def test_audit_log_permission_denied(db_session, test_tenant, test_user):
    """Permission denial is logged with context."""
    entry = AuditLog(
        tenant_id=test_tenant.id,
        user_id=test_user.id,
        action=AuditAction.PERMISSION_DENIED,
        resource_type="vendor",
        details={
            "required": "vendors:edit",
            "had": ["vendors:view"],
            "endpoint": "/api/v1/vendors/123",
        },
    )
    db_session.add(entry)
    await db_session.commit()

    assert entry.action == AuditAction.PERMISSION_DENIED
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/db/test_audit_log_model.py -v`
Expected: FAIL with "No module named 'src.db.models.audit_log'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/db/models/audit_log.py
"""Audit log model for security tracking."""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, generate_uuid

if TYPE_CHECKING:
    from src.db.models.tenant import Tenant
    from src.db.models.user import User


class AuditAction(str, Enum):
    """Audit log action types."""
    # Auth events
    LOGIN = "login"
    LOGOUT = "logout"
    LOGIN_FAILED = "login_failed"
    PASSWORD_RESET = "password_reset"
    
    # User management
    USER_INVITED = "user_invited"
    USER_CREATED = "user_created"
    USER_UPDATED = "user_updated"
    USER_DEACTIVATED = "user_deactivated"
    
    # Role management
    ROLE_CREATED = "role_created"
    ROLE_UPDATED = "role_updated"
    ROLE_DELETED = "role_deleted"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_UNASSIGNED = "role_unassigned"
    
    # Permission events
    PERMISSION_DENIED = "permission_denied"
    
    # Resource events
    RESOURCE_CREATED = "resource_created"
    RESOURCE_UPDATED = "resource_updated"
    RESOURCE_DELETED = "resource_deleted"
    
    # Settings
    SETTINGS_UPDATED = "settings_updated"
    
    # Super admin
    IMPERSONATION_START = "impersonation_start"
    IMPERSONATION_END = "impersonation_end"


class AuditLog(Base):
    """Append-only audit log for security and compliance."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("idx_audit_log_tenant_created", "tenant_id", "created_at"),
        Index("idx_audit_log_user", "user_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,  # null for system events
    )
    action: Mapped[AuditAction] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True))
    details: Mapped[dict | None] = mapped_column(JSONB)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow,
        nullable=False,
    )

    # Relationships (read-only)
    tenant: Mapped["Tenant"] = relationship("Tenant", lazy="selectin")
    user: Mapped["User"] = relationship("User", lazy="selectin")

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} by {self.user_id}>"
```

**Step 4: Update exports**

```python
# Add to packages/api/src/db/models/__init__.py
from src.db.models.audit_log import AuditLog, AuditAction
```

**Step 5: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/db/test_audit_log_model.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/api/src/db/models/audit_log.py packages/api/src/db/models/__init__.py
git add packages/api/tests/db/test_audit_log_model.py
git commit -m "feat(api): add AuditLog model for security tracking"
```

---

## Task 4: Permission Definitions

**Files:**
- Create: `packages/api/src/auth/permissions.py`
- Test: `packages/api/tests/auth/test_permissions.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/auth/test_permissions.py
import pytest
from src.auth.permissions import Permission, RESOURCES, ACTIONS, ALL_PERMISSIONS


def test_permission_structure():
    """All permissions follow resource:action format."""
    for perm in ALL_PERMISSIONS:
        assert ":" in perm
        resource, action = perm.split(":", 1)
        assert resource in RESOURCES
        assert action in ACTIONS or action == "*"


def test_permission_enum_values():
    """Permission enum has expected values."""
    assert Permission.PRODUCTS_VIEW == "products:view"
    assert Permission.PURCHASE_ORDERS_RECEIVE == "purchase_orders:receive"
    assert Permission.ALL == "*:*"


def test_get_permissions_for_resource():
    """Can get all actions for a resource."""
    from src.auth.permissions import get_permissions_for_resource
    
    product_perms = get_permissions_for_resource("products")
    assert "products:view" in product_perms
    assert "products:create" in product_perms
    assert "products:edit" in product_perms
    assert "products:delete" in product_perms


def test_wildcard_matching():
    """Wildcard permissions match correctly."""
    from src.auth.permissions import permission_matches
    
    # Exact match
    assert permission_matches("products:view", "products:view")
    
    # Wildcard resource
    assert permission_matches("*:view", "products:view")
    
    # Wildcard action
    assert permission_matches("products:*", "products:view")
    assert permission_matches("products:*", "products:delete")
    
    # Full wildcard
    assert permission_matches("*:*", "anything:here")
    
    # No match
    assert not permission_matches("products:view", "vendors:view")
    assert not permission_matches("products:edit", "products:view")
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/auth/test_permissions.py -v`
Expected: FAIL with "No module named 'src.auth.permissions'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/auth/permissions.py
"""Permission definitions for Copio RBAC."""

from enum import Enum
from typing import List

# Resource types
RESOURCES = [
    "products",
    "inventory", 
    "vendors",
    "purchase_orders",
    "locations",
    "categories",
    "channels",
    "users",
    "roles",
    "settings",
    "audit_log",
]

# Action types
ACTIONS = [
    "view",
    "create",
    "edit",
    "delete",
    # Special actions
    "adjust",      # inventory
    "transfer",    # inventory
    "receive",     # purchase_orders
    "approve",     # purchase_orders
    "sync",        # channels
    "invite",      # users
    "export",      # audit_log
]

# Standard CRUD actions
CRUD_ACTIONS = ["view", "create", "edit", "delete"]

# Resource-specific actions
RESOURCE_ACTIONS = {
    "products": CRUD_ACTIONS,
    "inventory": ["view", "adjust", "transfer"],
    "vendors": CRUD_ACTIONS,
    "purchase_orders": CRUD_ACTIONS + ["receive", "approve"],
    "locations": CRUD_ACTIONS,
    "categories": CRUD_ACTIONS,
    "channels": CRUD_ACTIONS + ["sync"],
    "users": ["view", "edit", "delete", "invite"],
    "roles": CRUD_ACTIONS,
    "settings": ["view", "edit"],
    "audit_log": ["view", "export"],
}


def _generate_permissions() -> List[str]:
    """Generate all valid permission strings."""
    perms = []
    for resource, actions in RESOURCE_ACTIONS.items():
        for action in actions:
            perms.append(f"{resource}:{action}")
    return perms


ALL_PERMISSIONS = _generate_permissions()


class Permission(str, Enum):
    """All available permissions."""
    # Products
    PRODUCTS_VIEW = "products:view"
    PRODUCTS_CREATE = "products:create"
    PRODUCTS_EDIT = "products:edit"
    PRODUCTS_DELETE = "products:delete"
    
    # Inventory
    INVENTORY_VIEW = "inventory:view"
    INVENTORY_ADJUST = "inventory:adjust"
    INVENTORY_TRANSFER = "inventory:transfer"
    
    # Vendors
    VENDORS_VIEW = "vendors:view"
    VENDORS_CREATE = "vendors:create"
    VENDORS_EDIT = "vendors:edit"
    VENDORS_DELETE = "vendors:delete"
    
    # Purchase Orders
    PURCHASE_ORDERS_VIEW = "purchase_orders:view"
    PURCHASE_ORDERS_CREATE = "purchase_orders:create"
    PURCHASE_ORDERS_EDIT = "purchase_orders:edit"
    PURCHASE_ORDERS_DELETE = "purchase_orders:delete"
    PURCHASE_ORDERS_RECEIVE = "purchase_orders:receive"
    PURCHASE_ORDERS_APPROVE = "purchase_orders:approve"
    
    # Locations
    LOCATIONS_VIEW = "locations:view"
    LOCATIONS_CREATE = "locations:create"
    LOCATIONS_EDIT = "locations:edit"
    LOCATIONS_DELETE = "locations:delete"
    
    # Categories
    CATEGORIES_VIEW = "categories:view"
    CATEGORIES_CREATE = "categories:create"
    CATEGORIES_EDIT = "categories:edit"
    CATEGORIES_DELETE = "categories:delete"
    
    # Channels
    CHANNELS_VIEW = "channels:view"
    CHANNELS_CREATE = "channels:create"
    CHANNELS_EDIT = "channels:edit"
    CHANNELS_DELETE = "channels:delete"
    CHANNELS_SYNC = "channels:sync"
    
    # Users
    USERS_VIEW = "users:view"
    USERS_EDIT = "users:edit"
    USERS_DELETE = "users:delete"
    USERS_INVITE = "users:invite"
    
    # Roles
    ROLES_VIEW = "roles:view"
    ROLES_CREATE = "roles:create"
    ROLES_EDIT = "roles:edit"
    ROLES_DELETE = "roles:delete"
    
    # Settings
    SETTINGS_VIEW = "settings:view"
    SETTINGS_EDIT = "settings:edit"
    
    # Audit Log
    AUDIT_LOG_VIEW = "audit_log:view"
    AUDIT_LOG_EXPORT = "audit_log:export"
    
    # Wildcards
    ALL = "*:*"


def get_permissions_for_resource(resource: str) -> List[str]:
    """Get all permission strings for a resource."""
    actions = RESOURCE_ACTIONS.get(resource, [])
    return [f"{resource}:{action}" for action in actions]


def permission_matches(granted: str, required: str) -> bool:
    """Check if a granted permission covers the required permission.
    
    Supports wildcards:
    - "*:*" matches everything
    - "*:view" matches any resource with view action
    - "products:*" matches any action on products
    """
    if granted == "*:*":
        return True
    
    granted_resource, granted_action = granted.split(":", 1)
    required_resource, required_action = required.split(":", 1)
    
    resource_match = granted_resource == "*" or granted_resource == required_resource
    action_match = granted_action == "*" or granted_action == required_action
    
    return resource_match and action_match
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/auth/test_permissions.py -v`
Expected: PASS

**Step 5: Commit**

```bash
mkdir -p packages/api/src/auth packages/api/tests/auth
touch packages/api/src/auth/__init__.py packages/api/tests/auth/__init__.py
git add packages/api/src/auth/permissions.py packages/api/tests/auth/test_permissions.py
git add packages/api/src/auth/__init__.py packages/api/tests/auth/__init__.py
git commit -m "feat(api): add permission definitions for RBAC"
```

---

## Task 5: Permission Enforcement Service

**Files:**
- Create: `packages/api/src/auth/enforcer.py`
- Test: `packages/api/tests/auth/test_enforcer.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/auth/test_enforcer.py
import pytest
from uuid import uuid4
from src.auth.enforcer import PermissionEnforcer
from src.db.models.role import Role
from src.db.models.user_role import UserRole


@pytest.fixture
async def enforcer(db_session):
    """Create enforcer instance."""
    return PermissionEnforcer(db_session)


@pytest.fixture
async def admin_role(db_session, test_tenant):
    """Create admin role with all permissions."""
    role = Role(
        tenant_id=test_tenant.id,
        name="Admin",
        is_system=True,
        permissions=["*:*"],
    )
    db_session.add(role)
    await db_session.commit()
    return role


@pytest.fixture
async def viewer_role(db_session, test_tenant):
    """Create viewer role with view-only permissions."""
    role = Role(
        tenant_id=test_tenant.id,
        name="Viewer",
        is_system=True,
        permissions=["*:view"],
    )
    db_session.add(role)
    await db_session.commit()
    return role


@pytest.mark.asyncio
async def test_admin_has_all_permissions(enforcer, test_user, admin_role, db_session):
    """Admin role grants all permissions."""
    user_role = UserRole(user_id=test_user.id, role_id=admin_role.id)
    db_session.add(user_role)
    await db_session.commit()

    assert await enforcer.can(test_user, "products:create")
    assert await enforcer.can(test_user, "users:delete")
    assert await enforcer.can(test_user, "settings:edit")


@pytest.mark.asyncio
async def test_viewer_can_only_view(enforcer, test_user, viewer_role, db_session):
    """Viewer role only grants view permissions."""
    user_role = UserRole(user_id=test_user.id, role_id=viewer_role.id)
    db_session.add(user_role)
    await db_session.commit()

    assert await enforcer.can(test_user, "products:view")
    assert await enforcer.can(test_user, "vendors:view")
    assert not await enforcer.can(test_user, "products:create")
    assert not await enforcer.can(test_user, "users:delete")


@pytest.mark.asyncio
async def test_user_with_no_role_denied(enforcer, test_user):
    """User without roles is denied all permissions."""
    assert not await enforcer.can(test_user, "products:view")


@pytest.mark.asyncio
async def test_get_user_permissions(enforcer, test_user, db_session, test_tenant):
    """Can get all effective permissions for a user."""
    role = Role(
        tenant_id=test_tenant.id,
        name="Warehouse",
        permissions=["inventory:view", "inventory:adjust", "purchase_orders:receive"],
    )
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()

    perms = await enforcer.get_permissions(test_user)
    assert "inventory:view" in perms
    assert "inventory:adjust" in perms
    assert "purchase_orders:receive" in perms
    assert "products:delete" not in perms
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/auth/test_enforcer.py -v`
Expected: FAIL with "No module named 'src.auth.enforcer'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/auth/enforcer.py
"""Permission enforcement service."""

from typing import List, Set
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.permissions import permission_matches, ALL_PERMISSIONS
from src.db.models.user import User
from src.db.models.user_role import UserRole
from src.db.models.role import Role


class PermissionEnforcer:
    """Check and enforce user permissions."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self._cache: dict[UUID, Set[str]] = {}

    async def _load_permissions(self, user: User) -> Set[str]:
        """Load all permissions for a user from their roles."""
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
        """Check if user has a specific permission.
        
        Args:
            user: The user to check
            permission: The required permission (e.g., "products:create")
            
        Returns:
            True if user has the permission, False otherwise
        """
        granted_permissions = await self._load_permissions(user)
        
        for granted in granted_permissions:
            if permission_matches(granted, permission):
                return True
        return False

    async def get_permissions(self, user: User) -> List[str]:
        """Get all effective permissions for a user.
        
        Expands wildcards to concrete permissions.
        
        Returns:
            List of permission strings the user has
        """
        granted_permissions = await self._load_permissions(user)
        
        # Expand wildcards
        effective: Set[str] = set()
        for granted in granted_permissions:
            if granted == "*:*":
                return ALL_PERMISSIONS
            elif "*" in granted:
                # Expand wildcard
                for perm in ALL_PERMISSIONS:
                    if permission_matches(granted, perm):
                        effective.add(perm)
            else:
                effective.add(granted)
        
        return sorted(effective)

    def clear_cache(self, user_id: UUID | None = None):
        """Clear permission cache.
        
        Args:
            user_id: Clear specific user's cache, or all if None
        """
        if user_id:
            self._cache.pop(user_id, None)
        else:
            self._cache.clear()
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/auth/test_enforcer.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/api/src/auth/enforcer.py packages/api/tests/auth/test_enforcer.py
git commit -m "feat(api): add PermissionEnforcer service for RBAC checks"
```

---

## Task 6: Permission Dependency — FastAPI Integration

**Files:**
- Create: `packages/api/src/auth/dependencies.py`
- Modify: `packages/api/src/api/deps.py`
- Test: `packages/api/tests/auth/test_dependencies.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/auth/test_dependencies.py
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from src.auth.dependencies import require_permission, get_enforcer
from src.db.models.role import Role
from src.db.models.user_role import UserRole


@pytest.fixture
def app_with_protected_route(db_session):
    """Create test app with a protected route."""
    from src.api.deps import get_current_user_with_dev_bypass, get_db
    
    app = FastAPI()
    
    @app.get("/protected")
    async def protected_route(
        user = Depends(get_current_user_with_dev_bypass),
        _perm = Depends(require_permission("products:create")),
    ):
        return {"message": "success", "user": user.email}
    
    return app


@pytest.mark.asyncio
async def test_permission_granted(app_with_protected_route, test_user, test_tenant, db_session):
    """User with permission can access route."""
    # Create admin role
    role = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    async with AsyncClient(
        transport=ASGITransport(app=app_with_protected_route),
        base_url="http://test"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_permission_denied(app_with_protected_route, test_user, test_tenant, db_session):
    """User without permission gets 403."""
    # Create viewer role (no create permission)
    role = Role(tenant_id=test_tenant.id, name="Viewer", permissions=["*:view"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    async with AsyncClient(
        transport=ASGITransport(app=app_with_protected_route),
        base_url="http://test"
    ) as client:
        response = await client.get("/protected")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/auth/test_dependencies.py -v`
Expected: FAIL with "No module named 'src.auth.dependencies'"

**Step 3: Write minimal implementation**

```python
# packages/api/src/auth/dependencies.py
"""FastAPI dependencies for permission enforcement."""

from typing import Annotated, Callable

from fastapi import Depends, HTTPException, Request, status

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.enforcer import PermissionEnforcer
from src.db.models.user import User


async def get_enforcer(session: DbSession) -> PermissionEnforcer:
    """Get permission enforcer instance."""
    return PermissionEnforcer(session)


Enforcer = Annotated[PermissionEnforcer, Depends(get_enforcer)]


def require_permission(permission: str) -> Callable:
    """Dependency that requires a specific permission.
    
    Usage:
        @app.get("/products")
        async def list_products(
            user = Depends(get_current_user),
            _perm = Depends(require_permission("products:view")),
        ):
            ...
    """
    async def check_permission(
        request: Request,
        user: User = Depends(get_current_user_with_dev_bypass),
        enforcer: PermissionEnforcer = Depends(get_enforcer),
    ) -> None:
        if not await enforcer.can(user, permission):
            # TODO: Log to audit log
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {permission} required",
            )
    
    return check_permission


def require_any_permission(*permissions: str) -> Callable:
    """Dependency that requires any of the specified permissions.
    
    Usage:
        @app.get("/reports")
        async def reports(
            _perm = Depends(require_any_permission("reports:view", "admin:*")),
        ):
            ...
    """
    async def check_permissions(
        request: Request,
        user: User = Depends(get_current_user_with_dev_bypass),
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
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/auth/test_dependencies.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/api/src/auth/dependencies.py packages/api/tests/auth/test_dependencies.py
git commit -m "feat(api): add FastAPI permission dependencies"
```

---

## Task 7: Roles API — List and Create

**Files:**
- Create: `packages/api/src/api/v1/roles.py`
- Modify: `packages/api/src/api/v1/router.py`
- Test: `packages/api/tests/api/test_roles.py`

**Step 1: Write the failing test**

```python
# packages/api/tests/api/test_roles.py
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_roles(client: AsyncClient, test_tenant, db_session):
    """Can list roles for tenant."""
    from src.db.models.role import Role
    
    # Create some roles
    roles = [
        Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"], is_system=True),
        Role(tenant_id=test_tenant.id, name="Viewer", permissions=["*:view"], is_system=True),
        Role(tenant_id=test_tenant.id, name="Custom", permissions=["products:view"]),
    ]
    db_session.add_all(roles)
    await db_session.commit()
    
    response = await client.get("/api/v1/roles")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 3
    assert any(r["name"] == "Admin" for r in data)


@pytest.mark.asyncio
async def test_create_role(client: AsyncClient, admin_user):
    """Admin can create a custom role."""
    response = await client.post(
        "/api/v1/roles",
        json={
            "name": "Warehouse Staff",
            "description": "Inventory and receiving",
            "permissions": [
                "inventory:view",
                "inventory:adjust",
                "purchase_orders:view",
                "purchase_orders:receive",
            ],
        },
    )
    assert response.status_code == 201
    
    data = response.json()
    assert data["name"] == "Warehouse Staff"
    assert data["is_system"] is False
    assert "inventory:view" in data["permissions"]


@pytest.mark.asyncio
async def test_create_role_duplicate_name(client: AsyncClient, admin_user, test_tenant, db_session):
    """Cannot create role with duplicate name."""
    from src.db.models.role import Role
    
    existing = Role(tenant_id=test_tenant.id, name="Manager", permissions=["*:view"])
    db_session.add(existing)
    await db_session.commit()
    
    response = await client.post(
        "/api/v1/roles",
        json={"name": "Manager", "permissions": ["products:view"]},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_role_invalid_permission(client: AsyncClient, admin_user):
    """Cannot create role with invalid permission."""
    response = await client.post(
        "/api/v1/roles",
        json={"name": "Bad Role", "permissions": ["invalid:permission"]},
    )
    assert response.status_code == 422
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/api/test_roles.py -v`
Expected: FAIL with 404 (route not found)

**Step 3: Write minimal implementation**

```python
# packages/api/src/api/v1/roles.py
"""Roles API endpoints."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.dependencies import require_permission
from src.auth.permissions import ALL_PERMISSIONS
from src.db.models.role import Role
from src.db.models.user import User

router = APIRouter(prefix="/roles", tags=["roles"])


class RoleCreate(BaseModel):
    """Schema for creating a role."""
    name: str
    description: str | None = None
    permissions: List[str]

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        invalid = [p for p in v if p not in ALL_PERMISSIONS and p != "*:*" and "*" not in p]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")
        return v


class RoleResponse(BaseModel):
    """Schema for role response."""
    id: UUID
    name: str
    description: str | None
    is_system: bool
    permissions: List[str]
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[RoleResponse])
async def list_roles(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("roles:view")),
):
    """List all roles for the current tenant."""
    result = await session.execute(
        select(Role).where(Role.tenant_id == user.tenant_id).order_by(Role.name)
    )
    return result.scalars().all()


@router.post("", response_model=RoleResponse, status_code=status.HTTP_201_CREATED)
async def create_role(
    data: RoleCreate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("roles:create")),
):
    """Create a new custom role."""
    role = Role(
        tenant_id=user.tenant_id,
        name=data.name,
        description=data.description,
        permissions=data.permissions,
        is_system=False,
    )
    session.add(role)
    
    try:
        await session.commit()
        await session.refresh(role)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Role '{data.name}' already exists",
        )
    
    return role
```

**Step 4: Add router to main router**

```python
# Add to packages/api/src/api/v1/router.py
from src.api.v1.roles import router as roles_router

api_router.include_router(roles_router)
```

**Step 5: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/api/test_roles.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add packages/api/src/api/v1/roles.py packages/api/src/api/v1/router.py
git add packages/api/tests/api/test_roles.py
git commit -m "feat(api): add roles list and create endpoints"
```

---

## Task 8: Roles API — Get, Update, Delete

**Files:**
- Modify: `packages/api/src/api/v1/roles.py`
- Test: `packages/api/tests/api/test_roles.py` (add tests)

**Step 1: Write the failing tests**

```python
# Add to packages/api/tests/api/test_roles.py

@pytest.mark.asyncio
async def test_get_role(client: AsyncClient, test_tenant, db_session, admin_user):
    """Can get a specific role."""
    from src.db.models.role import Role
    
    role = Role(tenant_id=test_tenant.id, name="Test Role", permissions=["products:view"])
    db_session.add(role)
    await db_session.commit()
    
    response = await client.get(f"/api/v1/roles/{role.id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Test Role"


@pytest.mark.asyncio
async def test_update_role(client: AsyncClient, test_tenant, db_session, admin_user):
    """Can update a custom role."""
    from src.db.models.role import Role
    
    role = Role(tenant_id=test_tenant.id, name="Custom", permissions=["products:view"])
    db_session.add(role)
    await db_session.commit()
    
    response = await client.patch(
        f"/api/v1/roles/{role.id}",
        json={
            "name": "Updated Role",
            "permissions": ["products:view", "products:edit"],
        },
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated Role"
    assert "products:edit" in response.json()["permissions"]


@pytest.mark.asyncio
async def test_cannot_update_system_role(client: AsyncClient, test_tenant, db_session, admin_user):
    """Cannot update a system role."""
    from src.db.models.role import Role
    
    role = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"], is_system=True)
    db_session.add(role)
    await db_session.commit()
    
    response = await client.patch(
        f"/api/v1/roles/{role.id}",
        json={"permissions": ["products:view"]},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_role(client: AsyncClient, test_tenant, db_session, admin_user):
    """Can delete a custom role."""
    from src.db.models.role import Role
    
    role = Role(tenant_id=test_tenant.id, name="ToDelete", permissions=["products:view"])
    db_session.add(role)
    await db_session.commit()
    
    response = await client.delete(f"/api/v1/roles/{role.id}")
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_cannot_delete_system_role(client: AsyncClient, test_tenant, db_session, admin_user):
    """Cannot delete a system role."""
    from src.db.models.role import Role
    
    role = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"], is_system=True)
    db_session.add(role)
    await db_session.commit()
    
    response = await client.delete(f"/api/v1/roles/{role.id}")
    assert response.status_code == 403
```

**Step 2: Run test to verify it fails**

Run: `cd packages/api && python -m pytest tests/api/test_roles.py::test_get_role -v`
Expected: FAIL with 404 or 405

**Step 3: Add endpoints to roles.py**

```python
# Add to packages/api/src/api/v1/roles.py

class RoleUpdate(BaseModel):
    """Schema for updating a role."""
    name: str | None = None
    description: str | None = None
    permissions: List[str] | None = None

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str] | None) -> List[str] | None:
        if v is None:
            return v
        invalid = [p for p in v if p not in ALL_PERMISSIONS and p != "*:*" and "*" not in p]
        if invalid:
            raise ValueError(f"Invalid permissions: {invalid}")
        return v


@router.get("/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: UUID,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("roles:view")),
):
    """Get a specific role."""
    result = await session.execute(
        select(Role)
        .where(Role.id == role_id)
        .where(Role.tenant_id == user.tenant_id)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return role


@router.patch("/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: UUID,
    data: RoleUpdate,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("roles:edit")),
):
    """Update a custom role."""
    result = await session.execute(
        select(Role)
        .where(Role.id == role_id)
        .where(Role.tenant_id == user.tenant_id)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot modify system roles")
    
    if data.name is not None:
        role.name = data.name
    if data.description is not None:
        role.description = data.description
    if data.permissions is not None:
        role.permissions = data.permissions
    
    await session.commit()
    await session.refresh(role)
    return role


@router.delete("/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: UUID,
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("roles:delete")),
):
    """Delete a custom role."""
    result = await session.execute(
        select(Role)
        .where(Role.id == role_id)
        .where(Role.tenant_id == user.tenant_id)
    )
    role = result.scalar_one_or_none()
    
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    if role.is_system:
        raise HTTPException(status_code=403, detail="Cannot delete system roles")
    
    await session.delete(role)
    await session.commit()
```

**Step 4: Run test to verify it passes**

Run: `cd packages/api && python -m pytest tests/api/test_roles.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add packages/api/src/api/v1/roles.py packages/api/tests/api/test_roles.py
git commit -m "feat(api): add roles get, update, delete endpoints"
```

---

## Remaining Tasks (Summary)

### Task 9: Users API — List and Invite
- Create `packages/api/src/api/v1/users.py`
- Invite endpoint sends email, creates UserInvite
- Test invite creation and token generation

### Task 10: Users API — Accept Invite
- Validate token, create user, assign role
- Test accept flow with valid/invalid/expired tokens

### Task 11: Users API — Update and Deactivate
- PATCH for role changes, DELETE for deactivation
- Test role reassignment and deactivation

### Task 12: Audit Logging Service
- Create `packages/api/src/services/audit.py`
- Middleware for automatic logging
- Test audit events are recorded

### Task 13: Audit Log API
- GET with pagination and filters
- Export CSV endpoint
- Test filtering by action, user, date range

### Task 14: Permissions API
- GET /api/v1/permissions — list all available
- GET /api/v1/me/permissions — current user's effective
- Test permission listing

### Task 15: Frontend — Settings Layout
- Create `/settings` layout with sidebar
- Add navigation items for Users, Roles, Audit Log

### Task 16: Frontend — Roles List Page
- `/settings/roles` page with role cards
- Create role dialog
- Test role listing

### Task 17: Frontend — Role Editor with Permission Matrix
- `/settings/roles/[id]` page
- Checkbox matrix for permissions
- User assignment section

### Task 18: Frontend — Users Page
- `/settings/users` with user table
- Invite dialog
- Role assignment dropdown

### Task 19: Frontend — Audit Log Page
- `/settings/audit-log` with event list
- Filters and pagination
- Export button

### Task 20: Integration — Add Permission Checks to Existing Routes
- Add `require_permission` to products, vendors, POs, etc.
- Test existing routes respect permissions

---

**Plan complete. Saved to `docs/plans/2026-01-31-user-management-plan.md`.**
