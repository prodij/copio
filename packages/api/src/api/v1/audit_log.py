"""Audit Log API endpoints."""

import csv
import io
from datetime import datetime
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, desc, func

from src.api.deps import DbSession, get_current_user_with_dev_bypass
from src.auth.dependencies import require_permission
from src.db.models.audit_log import AuditLog, AuditAction
from src.db.models.user import User

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


class AuditLogEntry(BaseModel):
    """Audit log entry response model."""
    id: UUID
    user_id: UUID | None
    action: str
    resource_type: str | None
    resource_id: UUID | None
    details: dict | None
    ip_address: str | None
    created_at: datetime
    
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    """Paginated audit log response."""
    items: List[AuditLogEntry]
    total: int
    page: int
    page_size: int


@router.get("", response_model=AuditLogResponse)
async def list_audit_log(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("audit_log:view")),
    action: str | None = None,
    user_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """List audit log entries with pagination and filters."""
    query = select(AuditLog).where(AuditLog.tenant_id == user.tenant_id)
    
    if action:
        query = query.where(AuditLog.action == action)
    if user_id:
        query = query.where(AuditLog.user_id == user_id)
    
    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    count_result = await session.execute(count_query)
    total = count_result.scalar() or 0
    
    # Get page
    query = query.order_by(desc(AuditLog.created_at))
    query = query.offset((page - 1) * page_size).limit(page_size)
    
    result = await session.execute(query)
    items = result.scalars().all()
    
    return AuditLogResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/export")
async def export_audit_log(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm = Depends(require_permission("audit_log:export")),
):
    """Export audit log as CSV."""
    result = await session.execute(
        select(AuditLog)
        .where(AuditLog.tenant_id == user.tenant_id)
        .order_by(desc(AuditLog.created_at))
        .limit(10000)
    )
    entries = result.scalars().all()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["timestamp", "user_id", "action", "resource_type", "resource_id", "ip_address", "details"])
    
    for entry in entries:
        writer.writerow([
            entry.created_at.isoformat(),
            str(entry.user_id) if entry.user_id else "",
            entry.action.value if hasattr(entry.action, 'value') else str(entry.action),
            entry.resource_type or "",
            str(entry.resource_id) if entry.resource_id else "",
            entry.ip_address or "",
            str(entry.details) if entry.details else "",
        ])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=audit_log.csv"}
    )
