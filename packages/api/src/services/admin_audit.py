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
