"""Moves runs from the outbox (`sync_runs`) into the queue. The only code that writes queue jobs.

Two kinds of row need a queue job:
- new runs: `status = 'queued' and enqueued_at is null` (the outbox, rule 8);
- waiting runs (rate limited, report still processing) whose last queue job has finished: they get a
  new job scheduled at `next_attempt_at`.

Each row is locked with `for update skip locked`, deferred on the same connection and stamped in the
same transaction. So any number of dispatchers can run at once, and running one twice is harmless: a
row is either still unstamped (and locked by exactly one dispatcher) or stamped with a live job.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import text

from jobs.sync.engine import OutboxRow, ProcrastinateEngine

log = logging.getLogger(__name__)

_NEW = text("""
    select id, connection_id, dataset, kind from sync_runs
     where status = 'queued' and enqueued_at is null
     order by created_at
     limit :limit
     for update skip locked
""")

# A waiting run is due a new job once its previous job is no longer todo/doing (finished, failed, or
# deleted by the worker's cleanup). While that job is still running, the runner is the one that just
# set `waiting`, and its job ends right after. A run is put back only when it is nearly due: a future
# job would hold its stream's lock (Procrastinate orders a lock's jobs whether or not they are due).
_WAITING = text("""
    select r.id, r.connection_id, r.dataset, r.kind, r.next_attempt_at from sync_runs r
     where r.status = 'waiting' and r.next_attempt_at <= now() + make_interval(secs => :horizon)
       and not exists (select 1 from procrastinate_jobs j
                        where j.id = r.queue_job_id and j.status in ('todo', 'doing'))
     order by r.next_attempt_at
     limit :limit
     for update of r skip locked
""")


@dataclass(frozen=True)
class DispatchResult:
    new: list[uuid.UUID]
    resumed: list[uuid.UUID]

    @property
    def total(self) -> int:
        return len(self.new) + len(self.resumed)


class Dispatcher:
    def __init__(self, engine: ProcrastinateEngine, *, batch: int = 100, horizon_s: float = 5.0) -> None:
        self.engine = engine
        self.batch = batch
        self.horizon_s = horizon_s  # how early a waiting run may go back into the queue

    def dispatch(self) -> DispatchResult:
        """One pass. Each batch is one transaction: either every row in it is queued and stamped, or
        none is (and the next pass tries again)."""
        new: list[uuid.UUID] = []
        resumed: list[uuid.UUID] = []
        with self.engine.db.begin() as conn:
            for r in conn.execute(_NEW, {"limit": self.batch}).all():
                self.engine.enqueue_locked(conn, OutboxRow(r.id, r.connection_id, r.dataset, r.kind))
                new.append(r.id)
        with self.engine.db.begin() as conn:
            for r in conn.execute(_WAITING, {"limit": self.batch, "horizon": self.horizon_s}).all():
                self.engine.enqueue_locked(conn, OutboxRow(r.id, r.connection_id, r.dataset, r.kind),
                                           run_at=r.next_attempt_at)
                resumed.append(r.id)
        if new or resumed:
            log.info("dispatched %d new and %d waiting run(s)", len(new), len(resumed))
        return DispatchResult(new, resumed)

    def drain(self, max_passes: int = 100) -> int:
        """Dispatch until a pass finds nothing (or `max_passes`). Returns how many runs were queued."""
        total = 0
        for _ in range(max_passes):
            result = self.dispatch()
            total += result.total
            if len(result.new) < self.batch and len(result.resumed) < self.batch:
                break
        return total
