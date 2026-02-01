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
    
    with pytest.raises(Exception):
        await db_session.commit()
