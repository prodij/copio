"""Turns `sync_schedules` into runs. It only inserts outbox rows; the dispatcher queues them.

Each tick, for every schedule that is due (`next_due_at <= now`, or never evaluated), not paused, and
whose connection is `healthy`:

- Slots come from the schedule's cron evaluated in its own timezone (so "0 2 * * *" in
  Europe/Berlin stays at 02:00 local across daylight-saving changes) and stored in UTC.
- `next_due_at` is the next slot plus a per-slot jitter in [0, jitter_s], derived from the stream and
  the slot, so every scheduler computes the same value and thousands of schedules on "0 * * * *" don't
  all hit a provider in the same second. Jitter is kept below the cron period.
- The run's window is [previous slot - lookback, slot): contiguous slot to slot, with `lookback_s`
  re-reading recent data that providers change after the fact.
- Missed slots (the scheduler was down): slots older than `catchup_window_s` are dropped (coverage shows
  the gap; an operator backfills it). The missed slots inside the catch-up window become one run whose
  window spans all of them.
- Overlap: `skip` creates nothing while the stream has a queued, running or waiting run; `queue_one`
  allows one queued run behind a running one, never two.

Two schedulers can tick at once: due rows are taken `for update skip locked`, the row's `next_due_at`
moves in the same transaction as the insert, and the run's dedupe key is unique.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from croniter import croniter
from sqlalchemy import Connection, Engine, text

from jobs.sync.contract import RunKind, RunSpec, Trigger, Window

log = logging.getLogger(__name__)

ConnectorVersion = Callable[[str], str]  # provider name -> connector version recorded on the run


def unversioned(provider: str) -> str:
    return f"{provider}@unversioned"


@dataclass(frozen=True)
class Schedule:
    connection_id: uuid.UUID
    dataset: str
    kind: str
    cron: str
    timezone: str
    jitter_s: int
    overlap: str
    catchup_window_s: int
    lookback_s: int
    next_due_at: datetime | None


# -- pure slot arithmetic ----------------------------------------------------------------------------


def _local(when: datetime, tz: str) -> datetime:
    return when.astimezone(ZoneInfo(tz))


def slot_at_or_before(cron: str, tz: str, when: datetime) -> datetime:
    """The latest cron slot <= `when`, in UTC."""
    local = _local(when, tz)
    it = croniter(cron, local + timedelta(microseconds=1))  # get_prev is strictly before its start
    prev: datetime = it.get_prev(datetime)
    return prev.astimezone(UTC)


def slot_after(cron: str, tz: str, when: datetime) -> datetime:
    """The earliest cron slot > `when`, in UTC."""
    nxt: datetime = croniter(cron, _local(when, tz)).get_next(datetime)
    return nxt.astimezone(UTC)


def slot_before(cron: str, tz: str, slot: datetime) -> datetime:
    """The cron slot strictly before `slot`, in UTC."""
    prev: datetime = croniter(cron, _local(slot, tz)).get_prev(datetime)
    return prev.astimezone(UTC)


def jitter_for(s: Schedule, slot: datetime) -> timedelta:
    """Deterministic in (stream, slot), in [0, jitter_s], and always shorter than the gap to the next
    slot, so a jittered due time still identifies its slot."""
    if s.jitter_s <= 0:
        return timedelta(0)
    period = (slot_after(s.cron, s.timezone, slot) - slot).total_seconds()
    bound = min(float(s.jitter_s), max(0.0, period - 1.0))
    digest = hashlib.sha256(f"{s.connection_id}:{s.dataset}:{slot.isoformat()}".encode()).digest()
    fraction = int.from_bytes(digest[:8], "big") / 2.0**64
    return timedelta(seconds=int(fraction * (bound + 1)) if bound >= 1 else 0)


def next_due(s: Schedule, after: datetime) -> datetime:
    slot = slot_after(s.cron, s.timezone, after)
    return slot + jitter_for(s, slot)


@dataclass(frozen=True)
class Plan:
    """What one due schedule should do at `now`."""

    window: Window | None  # None: create no run
    next_due_at: datetime
    reason: str


def plan(s: Schedule, now: datetime) -> Plan:
    """Pure: which window (if any) to run now, and when this schedule is next due. Overlap is applied
    by the caller, which needs the database."""
    latest = slot_at_or_before(s.cron, s.timezone, now)
    following = next_due(s, now)
    if s.next_due_at is None:
        # Never evaluated (a new schedule): run the slot that just passed.
        first = latest
    else:
        # The slot this schedule was waiting for: jitter is shorter than the period, so the latest slot
        # at or before the jittered due time is that slot.
        first = slot_at_or_before(s.cron, s.timezone, s.next_due_at)
    horizon = now - timedelta(seconds=s.catchup_window_s)
    if latest < horizon:
        return Plan(None, following, "missed slots are older than the catch-up window")
    if first < horizon:
        # Some missed slots are too old: start from the first slot inside the catch-up window.
        first = slot_after(s.cron, s.timezone, horizon - timedelta(microseconds=1))
    start = slot_before(s.cron, s.timezone, first) - timedelta(seconds=s.lookback_s)
    reason = "due" if first == latest else "catch-up"
    return Plan(Window(start, latest), following, reason)


# -- database --------------------------------------------------------------------------------------

_DUE = text("""
    select s.connection_id, s.dataset, s.kind, s.cron, s.timezone, s.jitter_s, s.overlap,
           s.catchup_window_s, s.lookback_s, s.next_due_at, c.workspace_id, c.provider
      from sync_schedules s
      join connections c on c.id = s.connection_id
     where not s.paused and c.state = 'healthy'
       and (s.next_due_at is null or s.next_due_at <= :now)
     order by s.next_due_at nulls first
     limit :limit
     for update of s skip locked
""")

_ACTIVE = text("""
    select count(*) filter (where status = 'queued') as queued,
           count(*) filter (where status in ('running', 'waiting')) as busy
      from sync_runs
     where connection_id = :connection_id and dataset = :dataset
       and status in ('queued', 'running', 'waiting')
""")

_INSERT_RUN = text("""
    insert into sync_runs (id, workspace_id, connection_id, dataset, kind, trigger, window_start,
                           window_end, connector_version, dedupe_key, status)
    values (:id, :workspace_id, :connection_id, :dataset, :kind, :trigger, :window_start, :window_end,
            :connector_version, :dedupe_key, 'queued')
    on conflict (dedupe_key) do nothing
    returning id
""")


@dataclass(frozen=True)
class TickResult:
    created: list[uuid.UUID]
    skipped: list[tuple[uuid.UUID, str, str]]  # (connection, dataset, reason)


class Scheduler:
    def __init__(self, db: Engine, *, connector_version: ConnectorVersion = unversioned,
                 batch: int = 500) -> None:
        self.db = db
        self.connector_version = connector_version
        self.batch = batch

    def tick(self, now: datetime | None = None) -> TickResult:
        now = now or datetime.now(UTC)
        created: list[uuid.UUID] = []
        skipped: list[tuple[uuid.UUID, str, str]] = []
        with self.db.begin() as conn:
            for row in conn.execute(_DUE, {"now": now, "limit": self.batch}).all():
                s = Schedule(row.connection_id, row.dataset, row.kind, row.cron, row.timezone,
                             row.jitter_s, row.overlap, row.catchup_window_s, row.lookback_s,
                             row.next_due_at)
                try:
                    p = plan(s, now)
                except (ValueError, KeyError) as exc:  # a bad cron or timezone: skip this one, loudly
                    log.error("schedule %s/%s is invalid: %r", s.connection_id, s.dataset, exc)
                    skipped.append((s.connection_id, s.dataset, "invalid schedule"))
                    continue
                reason = p.reason
                if p.window is not None:
                    blocked = self._overlap_blocks(conn, s)
                    if blocked:
                        reason = blocked
                    else:
                        run_id = self._insert(conn, s, row._mapping, p.window)
                        if run_id is not None:
                            created.append(run_id)
                        else:
                            reason = "duplicate"
                if p.window is None or reason not in ("due", "catch-up"):
                    skipped.append((s.connection_id, s.dataset, reason))
                conn.execute(text(
                    "update sync_schedules set next_due_at = :next,"
                    " last_enqueued_at = case when :created then :now else last_enqueued_at end"
                    " where connection_id = :connection_id and dataset = :dataset"),
                    {"next": p.next_due_at, "created": reason in ("due", "catch-up"), "now": now,
                     "connection_id": s.connection_id, "dataset": s.dataset})
        if created:
            log.info("scheduled %d run(s)", len(created))
        return TickResult(created, skipped)

    @staticmethod
    def _overlap_blocks(conn: Connection, s: Schedule) -> str | None:
        active = conn.execute(_ACTIVE, {"connection_id": s.connection_id, "dataset": s.dataset}).one()
        if s.overlap == "queue_one":
            return "overlap: a run is already queued" if active.queued else None
        return "overlap: a run is active" if (active.queued or active.busy) else None

    def _insert(self, conn: Connection, s: Schedule, row: Any, window: Window) -> uuid.UUID | None:
        spec = RunSpec(workspace_id=row["workspace_id"], connection_id=s.connection_id, dataset=s.dataset,
                       kind=RunKind(s.kind), trigger=Trigger.SCHEDULE, window=window,
                       connector_version=self.connector_version(str(row["provider"])))
        inserted = conn.execute(_INSERT_RUN, {
            "id": uuid.uuid4(), "workspace_id": spec.workspace_id, "connection_id": spec.connection_id,
            "dataset": spec.dataset, "kind": str(spec.kind), "trigger": str(spec.trigger),
            "window_start": window.start, "window_end": window.end,
            "connector_version": spec.connector_version, "dedupe_key": spec.dedupe_key(),
        }).first()
        return None if inserted is None else uuid.UUID(str(inserted.id))
