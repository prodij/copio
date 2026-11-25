"""Run list and detail, and the four actions: each writes one outbox row and one audit event, and
a refused action writes neither."""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.connectors.models import SyncRun, SyncSchedule
from app.connectors.runs_routes import sanitize
from app.workspaces.models import Workspace
from tests.test_health_routes import ago, make_conn, make_raw, make_run, make_stream


@pytest.fixture
def other_ws(db_session: Session) -> Workspace:
    ws = Workspace(name="Other", owner_user_id="u-other", zitadel_org_id="org-other", status="ready")
    db_session.add(ws)
    db_session.flush()
    return ws


def _audits(db: Session, action: str | None = None) -> list[AuditEvent]:
    q = select(AuditEvent).order_by(AuditEvent.id)
    if action:
        q = q.where(AuditEvent.action == action)
    return list(db.scalars(q))


def _runs(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(SyncRun)) or 0


def _assert_outbox(db: Session, body: dict[str, Any]) -> SyncRun:
    run = db.get(SyncRun, uuid.UUID(body["id"]))
    assert run is not None
    db.refresh(run)
    assert (run.status, run.enqueued_at, run.queue_job_id) == ("queued", None, None)
    return run


def _assert_audit(db: Session, action: str, run: SyncRun, **detail: str) -> None:
    [event] = _audits(db, action)
    assert (event.actor_type, event.actor_id, event.target_type, event.target_id) == \
        ("user", "user-1", "sync_run", str(run.id))
    assert event.workspace_id == run.workspace_id
    assert event.detail.items() >= ({"connection_id": str(run.connection_id), "dataset": run.dataset} | detail).items()


# ---------------------------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------------------------


def test_list_filters_and_scopes_to_the_workspace(client: TestClient, db_session: Session, owner_workspace: str,
                                                  owner_headers: dict[str, str], other_ws: Workspace) -> None:
    a = make_conn(db_session, owner_workspace, name="A")
    b = make_conn(db_session, owner_workspace, name="B")
    failed = make_run(db_session, a, status="failed", created=ago(minutes=3))
    ok = make_run(db_session, a, status="succeeded", created=ago(minutes=2))
    other = make_run(db_session, b, status="failed", dataset="refunds", created=ago(minutes=1))
    make_run(db_session, make_conn(db_session, other_ws.id), status="failed")

    def ids(**params: str) -> list[str]:
        r = client.get("/sync/runs", params=params, headers=owner_headers)
        assert r.status_code == 200, r.text
        return [x["id"] for x in r.json()]

    assert ids() == [str(other.id), str(ok.id), str(failed.id)]
    assert ids(status="failed") == [str(other.id), str(failed.id)]
    assert ids(connection_id=str(a.id)) == [str(ok.id), str(failed.id)]
    assert ids(dataset="refunds") == [str(other.id)]
    assert ids(limit="1") == [str(other.id)]
    assert ids(before=other.created_at.isoformat(), limit="1") == [str(ok.id)]


def test_detail_shows_counts_request_ref_and_a_sanitized_error(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    secret = "sk_live_" + "a" * 40
    run = make_run(db_session, conn, status="failed", stage="fetching", attempt=5, records_accepted=12,
                   records_rejected=1, records_stale=3, error_code="http_400", provider_request_ref="req-123",
                   error_detail=f"400 from provider; Authorization: Bearer abc.def token={secret} {secret}")
    make_raw(db_session, run, 1)
    make_raw(db_session, run, 2, processed=True)

    r = client.get(f"/sync/runs/{run.id}", headers=owner_headers)
    assert r.status_code == 200, r.text
    d = r.json()
    assert (d["stage"], d["attempt"], d["trigger"], d["connector_version"]) == ("fetching", 5, "schedule", "synthetic-1.0")
    assert (d["records_accepted"], d["records_rejected"], d["records_stale"]) == (12, 1, 3)
    assert (d["raw_objects"], d["raw_unprocessed"], d["provider_request_ref"]) == (2, 1, "req-123")
    assert "abc.def" not in d["error_detail"] and secret not in d["error_detail"]
    assert d["error_detail"].startswith("400 from provider")


def test_sanitize_truncates_and_leaves_plain_text() -> None:
    assert sanitize(None) is None
    assert sanitize("timeout after 30s") == "timeout after 30s"
    long = sanitize("x " * 600)
    assert long is not None and len(long) == 501


def test_another_workspaces_runs_are_not_found(client: TestClient, db_session: Session,
                                               owner_headers: dict[str, str], other_ws: Workspace) -> None:
    theirs = make_conn(db_session, other_ws.id)
    failed = make_run(db_session, theirs, status="failed")
    waiting = make_run(db_session, theirs, status="waiting")
    make_raw(db_session, failed, 1)
    make_stream(db_session, theirs)
    before = _runs(db_session)
    for method, path in [("GET", f"/sync/runs/{failed.id}"), ("POST", f"/sync/runs/{failed.id}/retry"),
                         ("POST", f"/sync/runs/{failed.id}/replay"), ("POST", f"/sync/runs/{waiting.id}/resume"),
                         ("POST", f"/sync/connections/{theirs.id}/datasets/orders/refresh")]:
        r = client.request(method, path, headers=owner_headers)
        assert r.status_code == 404, (path, r.text)
    assert _runs(db_session) == before
    assert _audits(db_session) == []
    db_session.refresh(waiting)
    assert waiting.status == "waiting"


# ---------------------------------------------------------------------------------------------
# Refresh now
# ---------------------------------------------------------------------------------------------


def test_refresh_writes_a_manual_outbox_row_and_an_audit_event(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    covered_to = ago(hours=2)
    make_stream(db_session, conn, covered_to=covered_to)
    db_session.add(SyncSchedule(connection_id=conn.id, dataset="orders", cron="*/15 * * * *", lookback_s=600))
    make_run(db_session, conn, status="succeeded", connector_version="synthetic-2.1")

    r = client.post(f"/sync/connections/{conn.id}/datasets/orders/refresh", headers=owner_headers)
    assert r.status_code == 202, r.text
    run = _assert_outbox(db_session, r.json())
    assert (run.trigger, run.kind, run.requested_by, run.connector_version) == \
        ("manual", "incremental", "user-1", "synthetic-2.1")
    assert run.window_start == covered_to - timedelta(seconds=600)
    assert run.window_end > covered_to
    _assert_audit(db_session, "run.refresh", run)

    again = client.post(f"/sync/connections/{conn.id}/datasets/orders/refresh", headers=owner_headers)
    assert again.status_code == 409  # the first one is still queued
    assert len(_audits(db_session)) == 1


@pytest.mark.parametrize("state", ["paused", "reconnect_needed", "disconnected"])
def test_refresh_is_refused_unless_the_connection_is_healthy(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str],
        state: str) -> None:
    conn = make_conn(db_session, owner_workspace, state=state, reason="token revoked")
    make_stream(db_session, conn, covered_to=ago(hours=1))
    before = _runs(db_session)
    r = client.post(f"/sync/connections/{conn.id}/datasets/orders/refresh", headers=owner_headers)
    assert r.status_code == 409
    assert state in r.json()["detail"]
    assert _runs(db_session) == before
    assert _audits(db_session) == []


def test_refresh_of_an_unknown_dataset_is_not_found(client: TestClient, db_session: Session, owner_workspace: str,
                                                    owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    r = client.post(f"/sync/connections/{conn.id}/datasets/nope/refresh", headers=owner_headers)
    assert r.status_code == 404


def test_first_refresh_of_a_scheduled_dataset_fetches_a_day(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    db_session.add(SyncSchedule(connection_id=conn.id, dataset="report_daily", kind="report", cron="0 3 * * *"))
    db_session.flush()
    r = client.post(f"/sync/connections/{conn.id}/datasets/report_daily/refresh", headers=owner_headers)
    assert r.status_code == 202, r.text
    run = _assert_outbox(db_session, r.json())
    assert run.kind == "report"
    assert run.connector_version == "unknown"
    assert run.window_end - run.window_start == timedelta(days=1)


# ---------------------------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------------------------


def test_retry_copies_the_failed_run_with_its_checkpoint(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    failed = make_run(db_session, conn, status="failed", kind="report", stage="requested",
                      checkpoint={"report_id": "rpt-1"}, error_code="http_500", attempt=5)

    r = client.post(f"/sync/runs/{failed.id}/retry", headers=owner_headers)
    assert r.status_code == 202, r.text
    run = _assert_outbox(db_session, r.json())
    assert run.id != failed.id
    assert (run.trigger, run.kind, run.attempt, run.checkpoint) == ("retry", "report", 0, {"report_id": "rpt-1"})
    assert (run.window_start, run.window_end) == (failed.window_start, failed.window_end)
    _assert_audit(db_session, "run.retry", run, retry_of=str(failed.id))

    assert client.post(f"/sync/runs/{failed.id}/retry", headers=owner_headers).status_code == 409
    health = client.get(f"/sync/connections/{conn.id}/health", headers=owner_headers).json()
    assert health["connection"]["failed_runs_awaiting_action"] == 0


@pytest.mark.parametrize("run_status", ["succeeded", "queued", "running", "waiting", "cancelled"])
def test_only_a_failed_run_can_be_retried(client: TestClient, db_session: Session, owner_workspace: str,
                                          owner_headers: dict[str, str], run_status: str) -> None:
    run = make_run(db_session, make_conn(db_session, owner_workspace), status=run_status)
    before = _runs(db_session)
    assert client.post(f"/sync/runs/{run.id}/retry", headers=owner_headers).status_code == 409
    assert _runs(db_session) == before
    assert _audits(db_session) == []


def test_retry_is_refused_for_a_paused_connection(client: TestClient, db_session: Session, owner_workspace: str,
                                                  owner_headers: dict[str, str]) -> None:
    run = make_run(db_session, make_conn(db_session, owner_workspace, state="paused"), status="failed")
    assert client.post(f"/sync/runs/{run.id}/retry", headers=owner_headers).status_code == 409
    assert _audits(db_session) == []


# ---------------------------------------------------------------------------------------------
# Resume
# ---------------------------------------------------------------------------------------------


def test_resume_puts_the_waiting_run_back_in_the_outbox(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    waiting = make_run(db_session, conn, status="waiting", stage="requested", checkpoint={"report_id": "r"},
                       next_attempt_at=ago(minutes=-30), wait_reason="report processing", queue_job_id=77)
    before = _runs(db_session)

    r = client.post(f"/sync/runs/{waiting.id}/resume", headers=owner_headers)
    assert r.status_code == 202, r.text
    assert r.json()["id"] == str(waiting.id)
    run = _assert_outbox(db_session, r.json())
    assert (run.stage, run.checkpoint, run.wait_reason) == ("requested", {"report_id": "r"}, None)
    assert run.next_attempt_at is not None and run.next_attempt_at <= datetime.now(UTC)
    assert _runs(db_session) == before
    _assert_audit(db_session, "run.resume", run, wait_reason="report processing")

    assert client.post(f"/sync/runs/{waiting.id}/resume", headers=owner_headers).status_code == 409


def test_resume_is_refused_when_the_connection_needs_reconnecting(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace, state="reconnect_needed")
    waiting = make_run(db_session, conn, status="waiting")
    assert client.post(f"/sync/runs/{waiting.id}/resume", headers=owner_headers).status_code == 409
    db_session.refresh(waiting)
    assert waiting.status == "waiting"
    assert _audits(db_session) == []


# ---------------------------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------------------------


def test_replay_queues_a_replay_of_the_stored_raw(client: TestClient, db_session: Session, owner_workspace: str,
                                                  owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace, state="reconnect_needed")  # replay never calls the provider
    source = make_run(db_session, conn, status="succeeded", connector_version="synthetic-1.0")
    make_raw(db_session, source, 1, processed=True)
    make_raw(db_session, source, 2, processed=True)

    r = client.post(f"/sync/runs/{source.id}/replay", headers=owner_headers)
    assert r.status_code == 202, r.text
    run = _assert_outbox(db_session, r.json())
    assert (run.kind, run.trigger, run.replay_of, run.connector_version) == \
        ("replay", "manual", source.id, "synthetic-1.0")
    _assert_audit(db_session, "run.replay", run, replay_of=str(source.id), raw_objects="2")

    # One at a time; and replaying the replay replays the original raw.
    assert client.post(f"/sync/runs/{source.id}/replay", headers=owner_headers).status_code == 409
    run.status = "succeeded"
    db_session.flush()
    again = client.post(f"/sync/runs/{run.id}/replay", headers=owner_headers)
    assert again.status_code == 202, again.text
    assert again.json()["replay_of"] == str(source.id)


def test_replay_needs_stored_raw_and_a_finished_run(client: TestClient, db_session: Session, owner_workspace: str,
                                                    owner_headers: dict[str, str]) -> None:
    conn = make_conn(db_session, owner_workspace)
    empty = make_run(db_session, conn, status="failed")
    running = make_run(db_session, conn, status="running")
    make_raw(db_session, running, 1)
    assert client.post(f"/sync/runs/{empty.id}/replay", headers=owner_headers).status_code == 409
    assert client.post(f"/sync/runs/{running.id}/replay", headers=owner_headers).status_code == 409
    assert _audits(db_session) == []


def test_replay_is_refused_for_a_disconnected_connection(
        client: TestClient, db_session: Session, owner_workspace: str, owner_headers: dict[str, str]) -> None:
    source = make_run(db_session, make_conn(db_session, owner_workspace, state="disconnected"), status="failed")
    make_raw(db_session, source, 1)
    assert client.post(f"/sync/runs/{source.id}/replay", headers=owner_headers).status_code == 409
