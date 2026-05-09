from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.db import AuditLog


class AuditService:
    """Append-only audit log writer.

    Phase 1.0: plain append. Phase 1.1 adds hash chain + DB trigger
    blocking UPDATE/DELETE.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        *,
        tenant_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        diagnostic_id: UUID | str | None = None,
    ) -> AuditLog:
        diag = UUID(str(diagnostic_id)) if diagnostic_id else None
        entry = AuditLog(
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
            diagnostic_id=diag,
        )
        self.session.add(entry)
        await self.session.commit()
        await self.session.refresh(entry)
        return entry
