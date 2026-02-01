# packages/api/tests/services/test_audit.py
import pytest
from sqlalchemy import select
from src.services.audit import AuditService
from src.db.models.audit_log import AuditLog, AuditAction


@pytest.mark.asyncio
async def test_log_login(db_session, test_tenant, test_user):
    service = AuditService(db_session)
    await service.log_login(test_user, ip_address="192.168.1.1", user_agent="Mozilla/5.0")
    
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == AuditAction.LOGIN)
    )
    log = result.scalar_one()
    assert log.user_id == test_user.id
    assert str(log.ip_address) == "192.168.1.1"


@pytest.mark.asyncio
async def test_log_permission_denied(db_session, test_tenant, test_user):
    service = AuditService(db_session)
    await service.log_permission_denied(
        test_user,
        permission="vendors:edit",
        resource_type="vendor",
        ip_address="10.0.0.1",
    )
    
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.action == AuditAction.PERMISSION_DENIED)
    )
    log = result.scalar_one()
    assert log.details["permission"] == "vendors:edit"


@pytest.mark.asyncio
async def test_log_resource_change(db_session, test_tenant, test_user):
    from uuid import uuid4
    
    service = AuditService(db_session)
    resource_id = uuid4()
    await service.log_resource_change(
        test_user,
        action=AuditAction.RESOURCE_DELETED,
        resource_type="product",
        resource_id=resource_id,
        details={"sku": "ABC123"},
    )
    
    result = await db_session.execute(
        select(AuditLog).where(AuditLog.resource_id == resource_id)
    )
    log = result.scalar_one()
    assert log.action == AuditAction.RESOURCE_DELETED
    assert log.details["sku"] == "ABC123"
