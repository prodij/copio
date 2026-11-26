"""Read-only views of the connector layer for operators: which datasets are complete and fresh, and
what in the workspace needs attention. Everything is scoped to the caller's workspace.

Freshness comes from published coverage (`sync_streams.covered_to`), never from run status: a dataset
whose latest run succeeded is still stale when its coverage is older than its freshness target.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import ColumnElement, and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.connectors.models import Connection, RawObject, SyncRun, SyncSchedule, SyncStream
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter(prefix="/sync", tags=["sync"])

ACTIVE = ("queued", "running", "waiting")
# Error codes and wait reasons the runner and ledger write. Matching is deliberately loose on wait
# reasons, which are free text.
RATE_LIMIT_CODES = ("rate_limited", "http_429")
AUTH_CODES = ("auth_revoked", "auth_failed")
RECENT = timedelta(hours=24)

Freshness = Literal["fresh", "stale", "never_synced", "no_target"]


def now() -> datetime:
    return datetime.now(UTC)


def get_connection(session: Session, current: CurrentWorkspace, connection_id: uuid.UUID) -> Connection:
    """The connection if it belongs to the caller's workspace; 404 otherwise (never 403, so ids of
    other workspaces are not confirmed to exist)."""
    conn = session.get(Connection, connection_id)
    if conn is None or conn.workspace_id != current.workspace.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return conn


def awaiting_action() -> ColumnElement[bool]:
    """A failed run nobody has dealt with: no later run on the same stream covers its window and is
    queued, running, waiting or succeeded, and published coverage does not already include it."""
    later = aliased(SyncRun)
    superseded = exists().where(
        later.connection_id == SyncRun.connection_id,
        later.dataset == SyncRun.dataset,
        later.created_at > SyncRun.created_at,
        later.window_start <= SyncRun.window_start,
        later.window_end >= SyncRun.window_end,
        later.status.in_((*ACTIVE, "succeeded")),
    )
    covered = exists().where(
        SyncStream.connection_id == SyncRun.connection_id,
        SyncStream.dataset == SyncRun.dataset,
        SyncStream.covered_from <= SyncRun.window_start,
        SyncStream.covered_to >= SyncRun.window_end,
    )
    return and_(SyncRun.status == "failed", ~superseded, ~covered)


# ---------------------------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------------------------


class Period(BaseModel):
    start: datetime
    end: datetime


class RunBrief(BaseModel):
    id: uuid.UUID
    kind: str
    trigger: str
    status: str
    stage: str
    created_at: datetime
    finished_at: datetime | None
    error_code: str | None


class DatasetHealth(BaseModel):
    """`last_publish_*` is the last complete publication; `last_attempt` is the newest run, whatever
    it did. They are separate on purpose."""

    dataset: str
    freshness: Freshness
    freshness_target_s: int | None
    lag_s: int | None  # now minus covered_to
    covered_from: datetime | None
    covered_to: datetime | None
    last_publish_at: datetime | None
    last_publish_run_id: uuid.UUID | None
    last_attempt_at: datetime | None
    last_attempt: RunBrief | None
    active_run_id: uuid.UUID | None
    missing_periods: list[Period]  # time after coverage that no run published or is working on
    replay_backlog: int  # raw objects saved but not yet published
    lease_expired: bool
    schedule_paused: bool | None  # None: no schedule for this dataset


class ConnectionSummary(BaseModel):
    id: uuid.UUID
    provider: str
    account_ref: str
    display_name: str
    state: str
    state_reason: str | None
    datasets: int
    stale_datasets: int
    failed_runs_awaiting_action: int
    last_publish_at: datetime | None


class ConnectionHealth(BaseModel):
    connection: ConnectionSummary
    datasets: list[DatasetHealth]
    checked_at: datetime


class StreamRef(BaseModel):
    connection_id: uuid.UUID
    dataset: str
    covered_to: datetime | None


class OperatorHealth(BaseModel):
    checked_at: datetime
    recent_window_s: int
    queued_runs: int
    outbox_pending: int  # queued runs the dispatcher has not handed to the queue yet
    oldest_queued_age_s: int | None
    oldest_unpublished: StreamRef | None  # the stream whose published coverage ends earliest
    oldest_unprocessed_raw_at: datetime | None
    rate_limited_recent: int  # runs that hit a 429 or waited on a rate limit in the recent window
    waiting_runs: int
    expired_leases: int
    reconnect_needed_connections: int
    auth_failures_recent: int
    failed_runs_awaiting_action: int


# ---------------------------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------------------------


def _subtract(period: Period, cov_from: datetime | None, cov_to: datetime | None) -> list[Period]:
    if cov_from is None or cov_to is None or period.end <= cov_from or period.start >= cov_to:
        return [period]
    pieces = []
    if period.start < cov_from:
        pieces.append(Period(start=period.start, end=cov_from))
    if period.end > cov_to:
        pieces.append(Period(start=cov_to, end=period.end))
    return pieces


def missing_periods(windows: list[tuple[datetime, datetime, str]], cov_from: datetime | None,
                    cov_to: datetime | None) -> list[Period]:
    """Time nobody has data for or is fetching: from the end of coverage (or the first attempt, if
    nothing was ever published) to the end of the latest attempted window, minus every window a run
    published or is still working on. That counts failed windows nobody retried, and also time no run
    ever asked for, such as slots the scheduler dropped after an outage longer than its catch-up."""
    if not windows:
        return []
    low = cov_to if cov_to is not None else min(start for start, _, _ in windows)
    high = max(end for _, end, _ in windows)
    gaps = [Period(start=low, end=high)] if high > low else []
    for start, end, run_status in sorted(windows):
        if run_status not in (*ACTIVE, "succeeded"):
            continue
        gaps = [piece for gap in gaps for piece in _subtract(gap, start, end)]
    return _merge([piece for gap in gaps for piece in _subtract(gap, cov_from, cov_to)])


def _merge(periods: list[Period]) -> list[Period]:
    merged: list[Period] = []
    for p in sorted(periods, key=lambda p: p.start):
        if merged and p.start <= merged[-1].end:
            merged[-1] = Period(start=merged[-1].start, end=max(merged[-1].end, p.end))
        else:
            merged.append(p)
    return merged


def freshness_of(covered_to: datetime | None, target_s: int | None, at: datetime) -> tuple[Freshness, int | None]:
    if covered_to is None:
        return "never_synced", None
    lag = max(0, int((at - covered_to).total_seconds()))
    if target_s is None:
        return "no_target", lag
    return ("stale" if lag > target_s else "fresh"), lag


def _brief(run: SyncRun) -> RunBrief:
    return RunBrief(id=run.id, kind=run.kind, trigger=run.trigger, status=run.status, stage=run.stage,
                    created_at=run.created_at, finished_at=run.finished_at, error_code=run.error_code)


@dataclass
class _Stream:
    dataset: str
    stream: SyncStream | None
    schedule: SyncSchedule | None


def dataset_health(session: Session, conn: Connection, at: datetime) -> list[DatasetHealth]:
    streams = {s.dataset: s for s in session.scalars(
        select(SyncStream).where(SyncStream.connection_id == conn.id))}
    schedules = {s.dataset: s for s in session.scalars(
        select(SyncSchedule).where(SyncSchedule.connection_id == conn.id))}
    backlog: dict[str, int] = {name: n for name, n in session.execute(
        select(RawObject.dataset, func.count()).where(RawObject.connection_id == conn.id,
                                                      RawObject.processed_at.is_(None))
        .group_by(RawObject.dataset))}

    out = []
    for name in sorted(set(streams) | set(schedules) | set(backlog)):
        st = _Stream(name, streams.get(name), schedules.get(name))
        cov_from = st.stream.covered_from if st.stream else None
        cov_to = st.stream.covered_to if st.stream else None
        target = st.stream.freshness_target_s if st.stream else None
        fresh, lag = freshness_of(cov_to, target, at)
        last = session.scalars(select(SyncRun).where(SyncRun.connection_id == conn.id, SyncRun.dataset == name)
                               .order_by(SyncRun.created_at.desc()).limit(1)).first()
        active = session.scalars(select(SyncRun.id).where(
            SyncRun.connection_id == conn.id, SyncRun.dataset == name, SyncRun.status.in_(ACTIVE))
            .order_by(SyncRun.created_at.desc()).limit(1)).first()
        windows = session.execute(select(SyncRun.window_start, SyncRun.window_end, SyncRun.status).where(
            SyncRun.connection_id == conn.id, SyncRun.dataset == name,
            *([SyncRun.window_end > cov_to] if cov_to is not None else []))).all()
        missing = missing_periods([(w.window_start, w.window_end, w.status) for w in windows], cov_from, cov_to)
        lease_expired = bool(st.stream and st.stream.lease_run_id and st.stream.lease_expires_at
                             and st.stream.lease_expires_at < at)
        out.append(DatasetHealth(
            dataset=name, freshness=fresh, freshness_target_s=target, lag_s=lag,
            covered_from=cov_from, covered_to=cov_to,
            last_publish_at=st.stream.last_publish_at if st.stream else None,
            last_publish_run_id=st.stream.last_publish_run_id if st.stream else None,
            last_attempt_at=st.stream.last_attempt_at if st.stream else None,
            last_attempt=_brief(last) if last else None, active_run_id=active,
            missing_periods=missing, replay_backlog=backlog.get(name, 0), lease_expired=lease_expired,
            schedule_paused=st.schedule.paused if st.schedule else None,
        ))
    return out


def summarize(session: Session, conn: Connection, datasets: list[DatasetHealth]) -> ConnectionSummary:
    failed = session.scalar(select(func.count()).select_from(SyncRun)
                            .where(SyncRun.connection_id == conn.id, awaiting_action())) or 0
    published = [d.last_publish_at for d in datasets if d.last_publish_at]
    return ConnectionSummary(
        id=conn.id, provider=conn.provider, account_ref=conn.account_ref, display_name=conn.display_name,
        state=conn.state, state_reason=conn.state_reason, datasets=len(datasets),
        stale_datasets=sum(1 for d in datasets if d.freshness in ("stale", "never_synced")),
        failed_runs_awaiting_action=failed, last_publish_at=max(published) if published else None,
    )


# ---------------------------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------------------------

Current = Annotated[CurrentWorkspace, Depends(current_workspace)]
Db = Annotated[Session, Depends(get_session)]


@router.get("/connections", response_model=list[ConnectionSummary])
def list_connections(current: Current, session: Db) -> list[ConnectionSummary]:
    at = now()
    conns = session.scalars(select(Connection).where(Connection.workspace_id == current.workspace.id)
                            .order_by(Connection.display_name, Connection.id)).all()
    return [summarize(session, c, dataset_health(session, c, at)) for c in conns]


@router.get("/connections/{connection_id}/health", response_model=ConnectionHealth)
def connection_health(connection_id: uuid.UUID, current: Current, session: Db) -> ConnectionHealth:
    conn = get_connection(session, current, connection_id)
    at = now()
    datasets = dataset_health(session, conn, at)
    return ConnectionHealth(connection=summarize(session, conn, datasets), datasets=datasets, checked_at=at)


@router.get("/health", response_model=OperatorHealth)
def operator_health(current: Current, session: Db) -> OperatorHealth:
    ws = current.workspace.id
    at = now()
    since = at - RECENT
    in_ws = SyncRun.workspace_id == ws

    def count(*where: ColumnElement[bool]) -> int:
        return session.scalar(select(func.count()).select_from(SyncRun).where(in_ws, *where)) or 0

    oldest_queued = session.scalar(select(func.min(SyncRun.created_at)).where(in_ws, SyncRun.status == "queued"))
    stalest = session.scalars(select(SyncStream).where(SyncStream.workspace_id == ws)
                              .order_by(SyncStream.covered_to.asc().nulls_first()).limit(1)).first()
    oldest_raw = session.scalar(select(func.min(RawObject.fetched_at))
                                .where(RawObject.workspace_id == ws, RawObject.processed_at.is_(None)))
    touched = func.coalesce(SyncRun.finished_at, SyncRun.started_at, SyncRun.created_at) >= since
    rate_limited = or_(SyncRun.error_code.in_(RATE_LIMIT_CODES), SyncRun.wait_reason.ilike("%rate%limit%"),
                       SyncRun.wait_reason.ilike("%429%"))
    expired = session.scalar(select(func.count()).select_from(SyncStream).where(
        SyncStream.workspace_id == ws, SyncStream.lease_run_id.is_not(None),
        SyncStream.lease_expires_at < at)) or 0
    reconnect = session.scalar(select(func.count()).select_from(Connection).where(
        Connection.workspace_id == ws, Connection.state == "reconnect_needed")) or 0
    return OperatorHealth(
        checked_at=at, recent_window_s=int(RECENT.total_seconds()),
        queued_runs=count(SyncRun.status == "queued"),
        outbox_pending=count(SyncRun.status == "queued", SyncRun.enqueued_at.is_(None)),
        oldest_queued_age_s=max(0, int((at - oldest_queued).total_seconds())) if oldest_queued else None,
        oldest_unpublished=StreamRef(connection_id=stalest.connection_id, dataset=stalest.dataset,
                                     covered_to=stalest.covered_to) if stalest else None,
        oldest_unprocessed_raw_at=oldest_raw,
        rate_limited_recent=count(touched, rate_limited),
        waiting_runs=count(SyncRun.status == "waiting"),
        expired_leases=expired,
        reconnect_needed_connections=reconnect,
        auth_failures_recent=count(touched, SyncRun.error_code.in_(AUTH_CODES)),
        failed_runs_awaiting_action=count(awaiting_action()),
    )
