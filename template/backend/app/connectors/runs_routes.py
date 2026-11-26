"""Sync runs for operators: list and detail, and the four recovery actions.

The actions never talk to a queue. Each one writes an outbox row (`sync_runs` with status `queued` and
`enqueued_at` null) and an audit event in one transaction; the dispatcher hands the row to the queue.
Each action locks the connection row first, so two clicks on the same connection are serialized.
"""
import re
import uuid
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import record
from app.auth.deps import require_principal
from app.auth.principal import Principal
from app.connectors.health import ACTIVE, get_connection, now
from app.connectors.models import Connection, RawObject, SyncRun, SyncSchedule, SyncStream
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter(prefix="/sync", tags=["sync"])

# A refresh of a dataset that has never published fetches this far back.
FIRST_REFRESH_WINDOW = timedelta(days=1)
UNKNOWN_VERSION = "unknown"
ERROR_DETAIL_MAX = 500

Current = Annotated[CurrentWorkspace, Depends(current_workspace)]
Db = Annotated[Session, Depends(get_session)]
Actor = Annotated[Principal, Depends(require_principal)]


class RunOut(BaseModel):
    id: uuid.UUID
    connection_id: uuid.UUID
    dataset: str
    kind: str
    trigger: str
    status: str
    stage: str
    attempt: int
    max_attempts: int
    window_start: datetime
    window_end: datetime
    connector_version: str
    error_code: str | None
    records_accepted: int
    records_rejected: int
    records_stale: int
    replay_of: uuid.UUID | None
    next_attempt_at: datetime | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunDetail(RunOut):
    error_detail: str | None  # sanitized again on the way out, whatever was stored
    provider_request_ref: str | None
    wait_reason: str | None
    requested_by: str | None
    enqueued_at: datetime | None
    raw_objects: int
    raw_unprocessed: int


_SECRETS = [
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]+"), r"\1 [redacted]"),
    (re.compile(r"(?i)\b(token|secret|password|api[_-]?key|authorization|access_token|refresh_token)"
                r"(\s*[=:]\s*)\S+"), r"\1\2[redacted]"),
    (re.compile(r"\b[A-Za-z0-9_-]{32,}\b"), "[redacted]"),
]


def sanitize(detail: str | None) -> str | None:
    """Defense in depth: error_detail is stored sanitized, but an operator screen must never show a
    credential even if a writer slipped one in."""
    if detail is None:
        return None
    for pattern, repl in _SECRETS:
        detail = pattern.sub(repl, detail)
    return detail if len(detail) <= ERROR_DETAIL_MAX else detail[:ERROR_DETAIL_MAX] + "…"


def _out(run: SyncRun) -> RunOut:
    return RunOut.model_validate(run, from_attributes=True)


def _detail(session: Session, run: SyncRun) -> RunDetail:
    total, unprocessed = session.execute(
        select(func.count(), func.count().filter(RawObject.processed_at.is_(None)))
        .where(RawObject.run_id == run.id)).one()
    base = _out(run).model_dump()
    return RunDetail(**base, error_detail=sanitize(run.error_detail), provider_request_ref=run.provider_request_ref,
                     wait_reason=run.wait_reason, requested_by=run.requested_by, enqueued_at=run.enqueued_at,
                     raw_objects=total, raw_unprocessed=unprocessed)


def _get_run(session: Session, current: CurrentWorkspace, run_id: uuid.UUID) -> SyncRun:
    run = session.get(SyncRun, run_id)
    if run is None or run.workspace_id != current.workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    return run


# ---------------------------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------------------------


@router.get("/runs", response_model=list[RunOut])
def list_runs(
    current: Current, session: Db,
    connection_id: uuid.UUID | None = None,
    dataset: str | None = None,
    run_status: Annotated[str | None, Query(alias="status")] = None,
    kind: str | None = None,
    trigger: str | None = None,
    before: Annotated[datetime | None, Query(description="Only runs created before this time (paging)")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[RunOut]:
    q = select(SyncRun).where(SyncRun.workspace_id == current.workspace.id)
    if connection_id is not None:
        q = q.where(SyncRun.connection_id == connection_id)
    if dataset is not None:
        q = q.where(SyncRun.dataset == dataset)
    if run_status is not None:
        q = q.where(SyncRun.status == run_status)
    if kind is not None:
        q = q.where(SyncRun.kind == kind)
    if trigger is not None:
        q = q.where(SyncRun.trigger == trigger)
    if before is not None:
        q = q.where(SyncRun.created_at < before)
    runs = session.scalars(q.order_by(SyncRun.created_at.desc(), SyncRun.id).limit(limit)).all()
    return [_out(r) for r in runs]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(run_id: uuid.UUID, current: Current, session: Db) -> RunDetail:
    return _detail(session, _get_run(session, current, run_id))


# ---------------------------------------------------------------------------------------------
# Actions (outbox + audit, one transaction)
# ---------------------------------------------------------------------------------------------


def _lock_connection(session: Session, current: CurrentWorkspace, connection_id: uuid.UUID) -> Connection:
    get_connection(session, current, connection_id)  # 404 before locking anything
    conn = session.get(Connection, connection_id, with_for_update=True, populate_existing=True)
    if conn is None:  # deleted between the two reads
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return conn


def _require_healthy(conn: Connection, action: str) -> None:
    if conn.state != "healthy":
        reason = f" ({conn.state_reason})" if conn.state_reason else ""
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"Cannot {action}: the connection is {conn.state}{reason}")


def _has_active_run(session: Session, connection_id: uuid.UUID, dataset: str) -> bool:
    return session.scalar(select(SyncRun.id).where(
        SyncRun.connection_id == connection_id, SyncRun.dataset == dataset, SyncRun.status.in_(ACTIVE))
        .limit(1)) is not None


def _insert(session: Session, run: SyncRun, conflict: str) -> None:
    try:
        with session.begin_nested():
            session.add(run)
    except IntegrityError as exc:  # the dedupe key already exists: someone did this a moment ago
        raise HTTPException(status.HTTP_409_CONFLICT, conflict) from exc


def _audit(session: Session, current: CurrentWorkspace, actor: Principal, action: str, run: SyncRun,
           **detail: str) -> None:
    record(session, workspace_id=current.workspace.id, actor_type="user", actor_id=actor.user_id,
           action=action, target_type="sync_run", target_id=str(run.id),
           detail={"connection_id": str(run.connection_id), "dataset": run.dataset, **detail})


@router.post("/connections/{connection_id}/datasets/{dataset}/refresh", status_code=202,
             response_model=RunOut)
def refresh_now(connection_id: uuid.UUID, dataset: str, current: Current, session: Db, actor: Actor) -> RunOut:
    """Queue a manual incremental run from the end of published coverage to now. It goes through the
    same queue, leases and rate budgets as a scheduled run."""
    conn = _lock_connection(session, current, connection_id)
    _require_healthy(conn, "refresh")
    stream = session.get(SyncStream, (conn.id, dataset))
    schedule = session.get(SyncSchedule, (conn.id, dataset))
    if stream is None and schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dataset not found")
    if _has_active_run(session, conn.id, dataset):
        raise HTTPException(status.HTTP_409_CONFLICT, "A run for this dataset is already queued or running")
    end = now()
    lookback = timedelta(seconds=schedule.lookback_s if schedule else 0)
    start = stream.covered_to - lookback if stream and stream.covered_to else end - FIRST_REFRESH_WINDOW
    if start >= end:
        start = end - (lookback or timedelta(hours=1))
    kind = schedule.kind if schedule and schedule.kind in ("incremental", "report") else "incremental"
    previous = session.scalar(select(SyncRun.connector_version).where(
        SyncRun.connection_id == conn.id, SyncRun.dataset == dataset)
        .order_by(SyncRun.created_at.desc()).limit(1))
    run = SyncRun(
        workspace_id=current.workspace.id, connection_id=conn.id, dataset=dataset, kind=kind, trigger="manual",
        window_start=start, window_end=end, connector_version=previous or UNKNOWN_VERSION,
        dedupe_key=f"{conn.id}:{dataset}:{kind}:{start.isoformat()}:{end.isoformat()}",
        status="queued", requested_by=actor.user_id, enqueued_at=None,
    )
    _insert(session, run, "This refresh was already requested")
    _audit(session, current, actor, "run.refresh", run)
    session.commit()
    return _out(run)


@router.post("/runs/{run_id}/retry", status_code=202, response_model=RunOut)
def retry_run(run_id: uuid.UUID, current: Current, session: Db, actor: Actor) -> RunOut:
    """A failed run is terminal; retrying creates a new run for the same unit of work. The checkpoint
    is carried over, so a report that was already requested is polled, never requested again."""
    failed = _get_run(session, current, run_id)
    conn = _lock_connection(session, current, failed.connection_id)
    session.refresh(failed)
    if failed.status != "failed":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only a failed run can be retried; this one is {failed.status}")
    _require_healthy(conn, "retry")
    run = SyncRun(
        workspace_id=failed.workspace_id, connection_id=failed.connection_id, dataset=failed.dataset,
        kind=failed.kind, trigger="retry", window_start=failed.window_start, window_end=failed.window_end,
        connector_version=failed.connector_version, dedupe_key=f"retry:{failed.id}",
        status="queued", max_attempts=failed.max_attempts, checkpoint=dict(failed.checkpoint),
        replay_of=failed.replay_of, requested_by=actor.user_id, enqueued_at=None,
    )
    _insert(session, run, "This run was already retried")
    _audit(session, current, actor, "run.retry", run, retry_of=str(failed.id))
    session.commit()
    return _out(run)


@router.post("/runs/{run_id}/resume", status_code=202, response_model=RunOut)
def resume_run(run_id: uuid.UUID, current: Current, session: Db, actor: Actor) -> RunOut:
    """Run a waiting run now instead of at `next_attempt_at`. A waiting run is not finished, so it is
    put back in the outbox as it is (same id, stage and checkpoint) rather than copied. Rate budgets
    still apply when it runs."""
    run = _get_run(session, current, run_id)
    conn = _lock_connection(session, current, run.connection_id)
    session.refresh(run, with_for_update=True)
    if run.status != "waiting":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Only a waiting run can be resumed; this one is {run.status}")
    _require_healthy(conn, "resume")
    previous_wait = run.wait_reason or ""
    run.status, run.enqueued_at, run.queue_job_id = "queued", None, None
    run.next_attempt_at, run.wait_reason = now(), None
    _audit(session, current, actor, "run.resume", run, wait_reason=previous_wait)
    session.commit()
    return _out(run)


@router.post("/runs/{run_id}/replay", status_code=202, response_model=RunOut)
def replay_run(run_id: uuid.UUID, current: Current, session: Db, actor: Actor) -> RunOut:
    """Re-process a run's stored raw objects with the current parser. Never calls the provider, so it
    is allowed while a connection is paused or needs reconnecting, but not once it is disconnected."""
    source = _get_run(session, current, run_id)
    if source.kind == "replay" and source.replay_of is not None:
        source = _get_run(session, current, source.replay_of)  # the raw belongs to the original run
    conn = _lock_connection(session, current, source.connection_id)
    if conn.state == "disconnected":
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot replay: the connection is disconnected")
    if source.status in ACTIVE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot replay a run that is {source.status}")
    raw = session.scalar(select(func.count()).select_from(RawObject).where(RawObject.run_id == source.id)) or 0
    if raw == 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "This run has no stored raw data to replay")
    replays = session.scalars(select(SyncRun).where(SyncRun.replay_of == source.id, SyncRun.kind == "replay")).all()
    if any(r.status in ACTIVE for r in replays):
        raise HTTPException(status.HTTP_409_CONFLICT, "A replay of this run is already queued or running")
    run = SyncRun(
        workspace_id=source.workspace_id, connection_id=source.connection_id, dataset=source.dataset,
        kind="replay", trigger="manual", window_start=source.window_start, window_end=source.window_end,
        connector_version=source.connector_version, dedupe_key=f"replay:{source.id}:{len(replays) + 1}",
        status="queued", replay_of=source.id, requested_by=actor.user_id, enqueued_at=None,
    )
    _insert(session, run, "This replay was already requested")
    _audit(session, current, actor, "run.replay", run, replay_of=str(source.id), raw_objects=str(raw))
    session.commit()
    return _out(run)
