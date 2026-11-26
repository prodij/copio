"""PgAuditSink writes system rows to the append-only audit_events table. Synthetic data only."""

import uuid

import pytest
from sqlalchemy import Engine, text

from jobs.sync.audit import PgAuditSink
from jobs.sync.contract import AuditSink


def test_records_a_system_event(two_workspaces: tuple[str, str], clean_tables: Engine) -> None:
    ws = uuid.UUID(two_workspaces[0])
    sink: AuditSink = PgAuditSink(clean_tables)
    run_id = str(uuid.uuid4())
    sink.record(ws, "run.replay", "sync_run", run_id, {"raw_objects": 3, "coverage_advanced": True})
    with clean_tables.connect() as conn:
        rows = conn.execute(text("select workspace_id, actor_type, actor_id, action, target_type, target_id,"
                                 " detail from audit_events")).all()
    assert [tuple(r) for r in rows] == [(ws, "system", "sync-runner", "run.replay", "sync_run", run_id,
                                         {"raw_objects": 3, "coverage_advanced": True})]


def test_each_record_is_its_own_transaction(two_workspaces: tuple[str, str], clean_tables: Engine) -> None:
    ws = uuid.UUID(two_workspaces[0])
    sink = PgAuditSink(clean_tables, actor_id="sync-dispatcher")
    sink.record(ws, "run.replay", "sync_run", "r1", {})
    with pytest.raises(TypeError):
        sink.record(ws, "run.replay", "sync_run", "r2", {"blob": b"raw bytes"})  # not JSON: refused
    with pytest.raises(ValueError, match="action"):
        sink.record(ws, "x" * 65, "sync_run", "r3", {})
    with clean_tables.connect() as conn:
        rows = conn.execute(text("select actor_id, target_id from audit_events")).all()
    assert [tuple(r) for r in rows] == [("sync-dispatcher", "r1")]
