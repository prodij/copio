"""PgAuditSink: the jobs side's `AuditSink`, writing system rows to the append-only `audit_events`.

Spec: docs/superpowers/specs/2026-11-25-connector-layer-design.md (fixed rule 9). Operator actions are
audited by the backend (`app.audit.record`); this sink is for what the worker does on its own, such as a
replay it ran. The detail must be JSON and is stored as given, so callers pass ids, codes and counts,
never a credential or a payload.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import Engine, text


class PgAuditSink:
    """Implements `AuditSink`. Each `record` is its own transaction."""

    def __init__(self, engine: Engine, *, actor_id: str = "sync-runner") -> None:
        if not 0 < len(actor_id) <= 128:
            raise ValueError("actor_id must be 1-128 characters")
        self._engine = engine
        self._actor_id = actor_id

    def record(self, workspace_id: uuid.UUID, action: str, target_type: str, target_id: str,
               detail: Mapping[str, Any]) -> None:
        for name, value, limit in (("action", action, 64), ("target_type", target_type, 32),
                                   ("target_id", target_id, 128)):
            if not 0 < len(value) <= limit:
                raise ValueError(f"{name} must be 1-{limit} characters")
        payload = json.dumps(dict(detail), sort_keys=True, allow_nan=False)  # TypeError if not JSON
        with self._engine.begin() as conn:
            conn.execute(text(
                "insert into audit_events (workspace_id, actor_type, actor_id, action, target_type,"
                " target_id, detail) values (:ws, 'system', :actor, :action, :target_type, :target_id,"
                " cast(:detail as jsonb))"),
                {"ws": workspace_id, "actor": self._actor_id, "action": action,
                 "target_type": target_type, "target_id": target_id, "detail": payload})
