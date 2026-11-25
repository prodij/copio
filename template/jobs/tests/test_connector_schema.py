"""The connector layer's schema (migration 0004) as the jobs worker sees it."""

import pytest
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import DBAPIError

from jobs.sync import contract

TABLES = {"connections", "credentials", "sync_schedules", "sync_runs", "sync_streams", "raw_objects",
          "synced_records", "rate_budgets", "audit_events"}


def test_migrations_create_every_connector_table(pg_engine: Engine) -> None:
    assert set(inspect(pg_engine).get_table_names()) >= TABLES


def test_stored_vocabulary_matches_the_contract(pg_engine: Engine) -> None:
    checks = {c["name"]: c["sqltext"] for t in ("connections", "sync_runs")
              for c in inspect(pg_engine).get_check_constraints(t)}
    for state in contract.ConnectionState:
        assert f"'{state.value}'" in checks["ck_connections_state"]
    for status in contract.RunStatus:
        assert f"'{status.value}'" in checks["ck_sync_runs_status"]
    for kind in contract.RunKind:
        assert f"'{kind.value}'" in checks["ck_sync_runs_kind"]


def test_audit_events_are_append_only(two_workspaces: tuple[str, str], clean_tables: Engine) -> None:
    ws, _ = two_workspaces
    with clean_tables.begin() as conn:
        conn.execute(text(
            "insert into audit_events (workspace_id, actor_type, actor_id, action, target_type, target_id)"
            " values (:ws, 'system', 'test', 'connection.pause', 'connection', 'c1')"), {"ws": ws})
    for sql in ("update audit_events set action = 'x'", "delete from audit_events"):
        with pytest.raises(DBAPIError, match="append-only"), clean_tables.begin() as conn:
            conn.execute(text(sql))


def test_dedupe_key_names_the_unit_of_work() -> None:
    import uuid
    from datetime import UTC, datetime

    window = contract.Window(datetime(2026, 11, 1, tzinfo=UTC), datetime(2026, 11, 2, tzinfo=UTC))
    spec = contract.RunSpec(uuid.uuid4(), uuid.uuid4(), "orders", contract.RunKind.INCREMENTAL,
                            contract.Trigger.SCHEDULE, window, "synthetic-1")
    again = contract.RunSpec(spec.workspace_id, spec.connection_id, "orders", contract.RunKind.INCREMENTAL,
                             contract.Trigger.WEBHOOK, window, "synthetic-1")
    assert spec.dedupe_key() == again.dedupe_key()  # a webhook and a timer for the same window: one run
