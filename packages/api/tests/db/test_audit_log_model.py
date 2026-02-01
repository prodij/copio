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
