# packages/api/tests/auth/test_enforcer.py
import pytest
from uuid import uuid4
from src.auth.enforcer import PermissionEnforcer
from src.db.models.role import Role
from src.db.models.user_role import UserRole


@pytest.fixture
async def enforcer(db_session):
    return PermissionEnforcer(db_session)


@pytest.fixture
async def admin_role(db_session, test_tenant):
    role = Role(tenant_id=test_tenant.id, name="Admin", is_system=True, permissions=["*:*"])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest.fixture
async def viewer_role(db_session, test_tenant):
    role = Role(tenant_id=test_tenant.id, name="Viewer", is_system=True, permissions=["*:view"])
    db_session.add(role)
    await db_session.commit()
    return role


@pytest.mark.asyncio
async def test_admin_has_all_permissions(enforcer, test_user, admin_role, db_session):
    user_role = UserRole(user_id=test_user.id, role_id=admin_role.id)
    db_session.add(user_role)
    await db_session.commit()

    assert await enforcer.can(test_user, "products:create")
    assert await enforcer.can(test_user, "users:delete")
    assert await enforcer.can(test_user, "settings:edit")


@pytest.mark.asyncio
async def test_viewer_can_only_view(enforcer, test_user, viewer_role, db_session):
    user_role = UserRole(user_id=test_user.id, role_id=viewer_role.id)
    db_session.add(user_role)
    await db_session.commit()

    assert await enforcer.can(test_user, "products:view")
    assert await enforcer.can(test_user, "vendors:view")
    assert not await enforcer.can(test_user, "products:create")
    assert not await enforcer.can(test_user, "users:delete")


@pytest.mark.asyncio
async def test_user_with_no_role_denied(enforcer, test_user):
    assert not await enforcer.can(test_user, "products:view")


@pytest.mark.asyncio
async def test_get_user_permissions(enforcer, test_user, db_session, test_tenant):
    role = Role(tenant_id=test_tenant.id, name="Warehouse",
                permissions=["inventory:view", "inventory:adjust", "purchase_orders:receive"])
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
