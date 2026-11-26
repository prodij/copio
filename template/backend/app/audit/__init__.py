"""Append-only audit trail. Call `record` in the same session (transaction) as the change it describes."""
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.audit.models import AuditEvent

ActorType = Literal["user", "agent", "system"]


def record(session: Session, *, workspace_id: uuid.UUID, actor_type: ActorType, actor_id: str,
           action: str, target_type: str, target_id: str, detail: dict[str, Any] | None = None) -> None:
    session.add(AuditEvent(workspace_id=workspace_id, actor_type=actor_type, actor_id=actor_id,
                           action=action, target_type=target_type, target_id=target_id,
                           detail=detail or {}))
