# packages/api/tests/api/test_audit_log.py
"""Tests for Audit Log API endpoints."""

import pytest
from httpx import AsyncClient
from uuid import uuid4


async def create_superuser(session, tenant_id):
    """Create a superuser for testing."""
    from src.db.models.user import User
    user = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@example.com",
        hashed_password="placeholder",
        tenant_id=tenant_id,
        is_active=True,
        is_superuser=True,
        role="admin",
    )
    session.add(user)
    await session.flush()
    return user


@pytest.mark.asyncio
async def test_list_audit_log(client_with_db):
    """Test listing audit log entries."""
    from src.db.models.audit_log import AuditLog, AuditAction
    from src.db.models.tenant import Tenant
    
    client, session = client_with_db
    
    # Create test data - create superuser FIRST so dev bypass finds it
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    user = await create_superuser(session, tenant.id)
    
    # Create some audit entries
    entries = [
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGIN),
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.PERMISSION_DENIED),
    ]
    session.add_all(entries)
    await session.commit()
    
    response = await client.get("/api/v1/audit-log")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) >= 2


@pytest.mark.asyncio
async def test_filter_audit_log_by_action(client_with_db):
    """Test filtering audit log entries by action."""
    from src.db.models.audit_log import AuditLog, AuditAction
    from src.db.models.tenant import Tenant
    
    client, session = client_with_db
    
    # Create test data - create superuser FIRST so dev bypass finds it
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    user = await create_superuser(session, tenant.id)
    
    # Create entries with different actions
    entries = [
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGIN),
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGOUT),
    ]
    session.add_all(entries)
    await session.commit()
    
    response = await client.get("/api/v1/audit-log?action=login")
    assert response.status_code == 200
    
    data = response.json()
    assert all(item["action"] == "login" for item in data["items"])


@pytest.mark.asyncio
async def test_filter_audit_log_by_user_id(client_with_db):
    """Test filtering audit log entries by user ID."""
    from src.db.models.audit_log import AuditLog, AuditAction
    from src.db.models.tenant import Tenant
    from src.db.models.user import User
    
    client, session = client_with_db
    
    # Create test data - create superuser FIRST so dev bypass finds it
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    user1 = await create_superuser(session, tenant.id)
    
    # Non-superuser
    user2 = User(
        id=uuid4(),
        email=f"user-{uuid4().hex[:8]}@example.com",
        hashed_password="placeholder",
        tenant_id=tenant.id,
        is_active=True,
        role="member",
    )
    session.add(user2)
    await session.flush()
    
    # Create entries for different users
    entries = [
        AuditLog(tenant_id=tenant.id, user_id=user1.id, action=AuditAction.LOGIN),
        AuditLog(tenant_id=tenant.id, user_id=user2.id, action=AuditAction.LOGIN),
    ]
    session.add_all(entries)
    await session.commit()
    
    response = await client.get(f"/api/v1/audit-log?user_id={user1.id}")
    assert response.status_code == 200
    
    data = response.json()
    assert all(item["user_id"] == str(user1.id) for item in data["items"])


@pytest.mark.asyncio
async def test_audit_log_pagination(client_with_db):
    """Test audit log pagination."""
    from src.db.models.audit_log import AuditLog, AuditAction
    from src.db.models.tenant import Tenant
    
    client, session = client_with_db
    
    # Create test data - create superuser FIRST so dev bypass finds it
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    user = await create_superuser(session, tenant.id)
    
    # Create multiple entries
    entries = [
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGIN)
        for _ in range(5)
    ]
    session.add_all(entries)
    await session.commit()
    
    response = await client.get("/api/v1/audit-log?page=1&page_size=2")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data["items"]) == 2
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert data["total"] >= 5


@pytest.mark.asyncio
async def test_export_audit_log(client_with_db):
    """Test exporting audit log as CSV."""
    from src.db.models.audit_log import AuditLog, AuditAction
    from src.db.models.tenant import Tenant
    
    client, session = client_with_db
    
    # Create test data - create superuser FIRST so dev bypass finds it
    tenant = Tenant(id=uuid4(), name="Test Tenant", slug=f"test-{uuid4().hex[:8]}")
    session.add(tenant)
    await session.flush()
    
    user = await create_superuser(session, tenant.id)
    
    # Create some audit entries
    entries = [
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGIN),
        AuditLog(tenant_id=tenant.id, user_id=user.id, action=AuditAction.LOGOUT),
    ]
    session.add_all(entries)
    await session.commit()
    
    response = await client.get("/api/v1/audit-log/export")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    
    # Check CSV content
    content = response.text
    lines = content.strip().split("\n")
    assert len(lines) >= 3  # Header + 2 entries
    assert "timestamp" in lines[0]
    assert "action" in lines[0]
