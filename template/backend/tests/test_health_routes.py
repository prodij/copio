"""Dataset health, the connection list and operator health. All synthetic rows."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.connectors.models import Connection, RawObject, SyncRun, SyncSchedule, SyncStream
from app.workspaces.models import Workspace

NOW = datetime.now(UTC)


def ago(**kw: float) -> datetime:
    return NOW - timedelta(**kw)


def make_conn(db: Session, workspace_id: str | uuid.UUID, *, state: str = "healthy", name: str = "Demo shop",
              reason: str | None = None) -> Connection:
    conn = Connection(workspace_id=uuid.UUID(str(workspace_id)), provider="synthetic",
                      account_ref=f"acct-{uuid.uuid4().hex[:8]}", display_name=name, state=state,
                      state_reason=reason, scopes=[], config={})
    db.add(conn)
    db.flush()
    return conn


def make_run(db: Session, conn: Connection, *, dataset: str = "orders", status: str = "succeeded",
             created: datetime | None = None, start: datetime | None = None, end: datetime | None = None,
             **kw: Any) -> SyncRun:
    created = created or ago(minutes=5)
    run = SyncRun(workspace_id=conn.workspace_id, connection_id=conn.id, dataset=dataset,
                  kind=kw.pop("kind", "incremental"), trigger=kw.pop("trigger", "schedule"),
                  window_start=start or created - timedelta(hours=1), window_end=end or created,
                  connector_version=kw.pop("connector_version", "synthetic-1.0"),
                  dedupe_key=f"test:{uuid.uuid4()}", status=status, stage=kw.pop("stage", "pending"),
                  created_at=created, enqueued_at=kw.pop("enqueued_at", created), **kw)
    db.add(run)
    db.flush()
    return run


def make_stream(db: Session, conn: Connection, *, dataset: str = "orders", covered_to: datetime | None = None,
                covered_from: datetime | None = None, target_s: int | None = 3600, **kw: Any) -> SyncStream:
    stream = SyncStream(connection_id=conn.id, dataset=dataset, workspace_id=conn.workspace_id,
                        covered_from=covered_from or (covered_to - timedelta(days=30) if covered_to else None),
                        covered_to=covered_to, freshness_target_s=target_s, **kw)
    db.add(stream)
    db.flush()
    return stream


def make_raw(db: Session, run: SyncRun, seq: int, *, processed: bool = False) -> RawObject:
    raw = RawObject(run_id=run.id, workspace_id=run.workspace_id, connection_id=run.connection_id,
                    dataset=run.dataset, page_seq=seq, storage_key=f"raw/{run.id}/{seq}.json",
                    sha256="0" * 64, size_bytes=10, fetched_at=ago(minutes=4),
                    processed_at=ago(minutes=3) if processed else None)
    db.add(raw)
    db.flush()
    return raw


@pytest.fixture
def other_ws(db_session: Session) -> Workspace:
    ws = Workspace(name="Other", owner_user_id="u-other", zitadel_org_id="org-other", status="ready")
    db_session.add(ws)
    db_session.flush()
    return ws


def _dataset(body: dict[str, Any], name: str) -> dict[str, Any]:
    return next(d for d in body["datasets"] if d["dataset"] == name)


def test_a_stale_dataset_is_stale_even_when_its_latest_run_succeeded(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    green = make_run(db_session, conn, status="succeeded", stage="published", created=ago(minutes=2),
                     finished_at=ago(minutes=1))
    make_stream(db_session, conn, covered_to=ago(hours=3), target_s=3600, last_publish_at=ago(hours=3),
                last_attempt_at=ago(minutes=2))

    r = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers)
    assert r.status_code == 200, r.text
    orders = _dataset(r.json(), "orders")
    assert orders["last_attempt"]["status"] == "succeeded"
    assert orders["last_attempt"]["id"] == str(green.id)
    assert orders["freshness"] == "stale"
    assert orders["lag_s"] >= 3 * 3600 - 5
    assert r.json()["connection"]["stale_datasets"] == 1

    listed = client.get("/sync/connections", headers=owner_headers).json()
    assert [c["stale_datasets"] for c in listed] == [1]


def test_fresh_never_synced_and_no_target(client: TestClient, db_session: Session, owner_workspace: str,
                                          owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    make_stream(db_session, conn, dataset="orders", covered_to=ago(minutes=10), target_s=3600)
    make_stream(db_session, conn, dataset="refunds", covered_to=ago(days=9), target_s=None)
    db_session.add(SyncSchedule(connection_id=conn.id, dataset="payouts", cron="0 * * * *", paused=True))
    db_session.flush()

    body = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    assert [d["dataset"] for d in body["datasets"]] == ["orders", "payouts", "refunds"]
    assert _dataset(body, "orders")["freshness"] == "fresh"
    payouts = _dataset(body, "payouts")
    assert (payouts["freshness"], payouts["lag_s"], payouts["schedule_paused"]) == ("never_synced", None, True)
    assert _dataset(body, "refunds")["freshness"] == "no_target"
    assert body["connection"]["stale_datasets"] == 1  # never synced counts as stale; no target does not


def test_last_publication_is_kept_apart_from_the_last_attempt(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    published = make_run(db_session, conn, status="succeeded", created=ago(hours=2))
    failed = make_run(db_session, conn, status="failed", created=ago(minutes=10), error_code="http_500")
    make_stream(db_session, conn, covered_to=ago(hours=2), last_publish_at=ago(hours=2),
                last_publish_run_id=published.id, last_attempt_at=ago(minutes=10))

    orders = _dataset(client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json(), "orders")
    assert orders["last_publish_run_id"] == str(published.id)
    assert orders["last_attempt"]["id"] == str(failed.id)
    assert orders["last_attempt"]["status"] == "failed"


def test_missing_periods_and_replay_backlog(client: TestClient, db_session: Session, owner_workspace: str,
                                            owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    covered_to = ago(hours=6)
    make_stream(db_session, conn, covered_to=covered_to)
    # Fails across the coverage edge: only the part after covered_to is missing.
    make_run(db_session, conn, status="failed", created=ago(hours=4), start=ago(hours=7), end=ago(hours=5))
    # Fails, then a later retry is queued for the same window: being dealt with, not missing.
    make_run(db_session, conn, status="failed", created=ago(hours=3), start=ago(hours=5), end=ago(hours=2))
    make_run(db_session, conn, status="queued", trigger="retry", created=ago(hours=1), start=ago(hours=5),
             end=ago(hours=2))
    with_raw = make_run(db_session, conn, status="running", created=ago(minutes=30), start=ago(hours=2),
                        end=ago(minutes=30))
    make_raw(db_session, with_raw, 1)
    make_raw(db_session, with_raw, 2)
    make_raw(db_session, with_raw, 3, processed=True)

    body = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    orders = _dataset(body, "orders")
    assert [(datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]))
            for p in orders["missing_periods"]] == [(covered_to, ago(hours=5))]
    assert orders["replay_backlog"] == 2
    assert orders["active_run_id"] == str(with_raw.id)
    assert body["connection"]["failed_runs_awaiting_action"] == 1


def test_operator_health_counts_only_this_workspace(client: TestClient, db_session: Session, owner_workspace: str,
                                                    owner_headers: dict[str, str], other_ws: Workspace) -> None:
    conn = make_conn(db_session, owner_workspace)
    make_conn(db_session, owner_workspace, state="reconnect_needed", name="Revoked")
    make_run(db_session, conn, status="queued", created=ago(minutes=20), enqueued_at=None)
    make_run(db_session, conn, status="queued", created=ago(minutes=5))
    make_run(db_session, conn, status="waiting", wait_reason="rate limited: retry after 30s")
    make_run(db_session, conn, status="failed", error_code="rate_limited", created=ago(hours=1))
    make_run(db_session, conn, status="failed", error_code="auth_revoked", created=ago(hours=2))
    leased = make_run(db_session, conn, dataset="refunds", status="running")
    make_stream(db_session, conn, dataset="refunds", covered_to=ago(days=2), lease_run_id=leased.id,
                lease_owner="worker-1", lease_expires_at=ago(minutes=1))
    make_stream(db_session, conn, dataset="orders", covered_from=ago(minutes=30), covered_to=ago(minutes=1))
    make_raw(db_session, leased, 1)

    noise = make_conn(db_session, other_ws.id, state="reconnect_needed")
    for status in ("queued", "waiting", "failed"):
        make_run(db_session, noise, status=status, created=ago(days=3), error_code="auth_revoked",
                 enqueued_at=None)
    make_stream(db_session, noise, covered_to=ago(days=30))

    r = client.get("/sync/health", headers=owner_headers)
    assert r.status_code == 200, r.text
    h = r.json()
    assert h["queued_runs"] == 2
    assert h["outbox_pending"] == 1
    assert 20 * 60 - 5 <= h["oldest_queued_age_s"] <= 20 * 60 + 600
    assert h["oldest_unpublished"]["dataset"] == "refunds"
    assert h["oldest_unpublished"]["connection_id"] == str(conn.id)
    assert h["oldest_unprocessed_raw_at"] is not None
    assert h["waiting_runs"] == 1
    assert h["rate_limited_recent"] == 2
    assert h["expired_leases"] == 1
    assert h["reconnect_needed_connections"] == 1
    assert h["auth_failures_recent"] == 1
    assert h["failed_runs_awaiting_action"] == 2


def test_another_workspaces_connection_is_not_found(client: TestClient, db_session: Session, owner_workspace: str,
                                                    owner_headers: dict[str, str], other_ws: Workspace) -> None:
    mine = make_conn(db_session, owner_workspace, name="Mine")
    theirs = make_conn(db_session, other_ws.id, name="Theirs")
    make_stream(db_session, theirs, covered_to=ago(hours=1))

    assert client.get(f"/sync/connections/{theirs.id}/health", headers=owner_headers).status_code == 404
    assert client.get(f"/sync/connections/{uuid.uuid4()}/health", headers=owner_headers).status_code == 404
    assert [c["id"] for c in client.get("/sync/connections", headers=owner_headers).json()] == [str(mine.id)]


def test_health_routes_need_a_workspace(client: TestClient) -> None:
    assert client.get("/sync/connections").status_code == 401
    assert client.get("/sync/health").status_code == 401


def _periods(body: dict[str, Any], name: str = "orders") -> list[tuple[datetime, datetime]]:
    return [(datetime.fromisoformat(p["start"]), datetime.fromisoformat(p["end"]))
            for p in _dataset(body, name)["missing_periods"]]


def test_time_no_run_asked_for_is_missing(client: TestClient, db_session: Session, owner_workspace: str,
                                          owner_headers: dict[str, str]) -> None:
    # The scheduler was down past its catch-up window: runs resume hours after coverage ends, and
    # nothing ever asks for the time in between.
    conn = make_conn(db_session, owner_workspace)
    covered_to = ago(hours=10)
    make_stream(db_session, conn, covered_to=covered_to)
    make_run(db_session, conn, status="succeeded", created=ago(hours=2), start=ago(hours=3), end=ago(hours=2))
    make_run(db_session, conn, status="queued", created=ago(minutes=1), start=ago(hours=2), end=ago(hours=1))

    body = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    assert _periods(body) == [(covered_to, ago(hours=3))]


def test_never_published_counts_from_the_first_attempt(client: TestClient, db_session: Session,
                                                       owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    make_stream(db_session, conn)  # claimed, never published
    make_run(db_session, conn, status="failed", created=ago(hours=11), start=ago(hours=12), end=ago(hours=11))
    make_run(db_session, conn, status="failed", created=ago(hours=1), start=ago(hours=2), end=ago(hours=1))
    make_run(db_session, conn, status="running", created=ago(minutes=5), start=ago(hours=1), end=ago(minutes=5))

    body = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    assert _periods(body) == [(ago(hours=12), ago(hours=1))]


def test_nothing_is_missing_when_runs_follow_coverage(client: TestClient, db_session: Session,
                                                      owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    make_stream(db_session, conn, covered_to=ago(hours=1))
    make_run(db_session, conn, status="succeeded", created=ago(hours=1), start=ago(hours=2), end=ago(hours=1))
    make_run(db_session, conn, status="running", created=ago(minutes=1), start=ago(hours=1, minutes=5),
             end=ago(minutes=1))

    body = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    assert _periods(body) == []
