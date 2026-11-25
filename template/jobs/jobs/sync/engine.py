"""The queue: Procrastinate on the app's own Postgres (no new infrastructure).

A queue job carries one thing, the run id. Everything else (what to fetch, the credentials, the
checkpoint) is read from Postgres by the runner when the job starts, so nothing secret or large is ever
in `procrastinate_jobs`.

Fairness, per stream (one connection + dataset):
- Incremental, report and replay runs go to the `sync` queue; backfills go to `backfill`. The worker
  runs a separate loop with its own concurrency for each, so a flood of backfills can't take the slots
  incremental work needs.
- Every run job carries the lock `stream:<connection>:<dataset>`. Procrastinate never runs two jobs
  with the same lock at once, so a backfill and an incremental never touch one stream together.
- Within a lock Procrastinate picks the highest priority first. Incremental work has a higher priority
  than backfill, so an incremental queued behind ten backfill chunks of the same stream runs as soon as
  the current chunk finishes, not after all ten. (A backfill run must therefore be a bounded window.)

Only the dispatcher calls `enqueue_locked`, inside the transaction that stamps the outbox row, so a run
is in the queue exactly when its row says so.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import procrastinate
from procrastinate import PsycopgConnector, SyncPsycopgConnector
from procrastinate.manager import JobManager
from procrastinate.tasks import configure_task
from sqlalchemy import Connection, Engine, create_engine, text
from sqlalchemy.engine import make_url

from jobs.sync.contract import RunKind

log = logging.getLogger(__name__)

SYNC_QUEUE = "sync"
BACKFILL_QUEUE = "backfill"
MAINTENANCE_QUEUE = "maintenance"  # periodic work: scheduler, dispatcher sweep, stalled jobs, billing
RUN_TASK = "sync.run"
RETRY_STALLED_TASK = "sync.retry_stalled_jobs"

INCREMENTAL_PRIORITY = 10
BACKFILL_PRIORITY = 0

# A worker whose heartbeat is older than this is presumed dead and its running jobs are retried.
# Procrastinate's defaults: heartbeat every 10 s, a worker is stalled after 30 s.
STALLED_AFTER_S = 30.0

Executor = Callable[[uuid.UUID], None]


class ExecutorMissing(RuntimeError):
    """The worker was started without a run executor (the runner is wired in jobs/worker.py)."""


def _no_executor(run_id: uuid.UUID) -> None:
    raise ExecutorMissing(f"no run executor installed; run {run_id} left for a worker that has one")


def conninfo(database_url: str) -> str:
    """psycopg's conninfo for a SQLAlchemy URL (`postgresql+psycopg://…` → `postgresql://…`)."""
    return make_url(database_url).set(drivername="postgresql").render_as_string(hide_password=False)


def queue_for(kind: str) -> str:
    return BACKFILL_QUEUE if kind == RunKind.BACKFILL else SYNC_QUEUE


def priority_for(kind: str) -> int:
    return BACKFILL_PRIORITY if kind == RunKind.BACKFILL else INCREMENTAL_PRIORITY


def stream_lock(connection_id: uuid.UUID | str, dataset: str) -> str:
    return f"stream:{connection_id}:{dataset}"


@dataclass(frozen=True)
class OutboxRow:
    """What the queue needs to know about a run; never more."""

    id: uuid.UUID
    connection_id: uuid.UUID
    dataset: str
    kind: str


class ProcrastinateEngine:
    """Implements contract.Engine. One instance per process.

    `app` is the asynchronous app the worker runs. Deferring always happens on a connection the caller
    already holds (the outbox transaction), through a job manager whose connector never opens a pool.
    (Not a second App: Procrastinate renames its global builtin tasks for every App created.)
    """

    def __init__(self, database_url: str, *, executor: Executor | None = None,
                 db: Engine | None = None) -> None:
        self.database_url = database_url
        self.conninfo = conninfo(database_url)
        self.db = db or create_engine(database_url, pool_pre_ping=True)
        self.executor: Executor = executor or _no_executor
        # max_delay: on start, a periodic slot missed by less than this still runs (default 10 min).
        self.app = procrastinate.App(connector=PsycopgConnector(conninfo=self.conninfo),
                                     periodic_defaults={"max_delay": 900})
        self._deferrer = JobManager(connector=SyncPsycopgConnector())
        self._register()

    # -- tasks ---------------------------------------------------------------------------------

    def _register(self) -> None:
        # A crash that escapes the runner (database down, a bug) is retried a few times with growing
        # waits; provider errors never get here, the runner turns them into ledger state.
        crash_retry = procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5)

        def run(run_id: str) -> None:
            self.executor(uuid.UUID(run_id))

        self.app.task(name=RUN_TASK, queue=SYNC_QUEUE, retry=crash_retry)(run)

        async def retry_stalled_jobs(timestamp: int) -> None:
            await self.retry_stalled_jobs_async()

        self.app.periodic(cron="* * * * *", periodic_id="stalled")(
            self.app.task(name=RETRY_STALLED_TASK, queue=MAINTENANCE_QUEUE,
                          queueing_lock=RETRY_STALLED_TASK)(retry_stalled_jobs))

    def set_executor(self, executor: Executor) -> None:
        self.executor = executor

    # -- queueing ------------------------------------------------------------------------------

    def enqueue_locked(self, conn: Connection, row: OutboxRow, *, run_at: datetime | None = None,
                       queue: str | None = None) -> int:
        """Defer the run's job on `conn` and stamp its row, in the caller's transaction. The caller
        holds the row lock (select … for update), which is what makes this happen once."""
        driver = conn.connection.driver_connection
        job_id = configure_task(
            name=RUN_TASK,
            job_manager=self._deferrer,
            queue=queue or queue_for(row.kind),
            lock=stream_lock(row.connection_id, row.dataset),
            priority=priority_for(row.kind),
            schedule_at=run_at,
            connection=driver,
        ).defer(run_id=str(row.id))
        conn.execute(text("update sync_runs set enqueued_at = now(), queue_job_id = :job where id = :id"),
                     {"job": job_id, "id": row.id})
        return job_id

    def enqueue(self, run_id: uuid.UUID, *, run_at: datetime | None = None, queue: str = SYNC_QUEUE) -> None:
        """contract.Engine. Puts one run in the queue now if its row still needs it; a second call for
        the same run does nothing. `queue` applies only to non-backfill runs (backfills always go to
        the backfill queue, which is what keeps them away from incremental slots)."""
        with self.db.begin() as conn:
            found = conn.execute(text(
                "select id, connection_id, dataset, kind from sync_runs"
                " where id = :id and status = 'queued' and enqueued_at is null for update"),
                {"id": run_id}).first()
            if found is None:
                return
            row = OutboxRow(found.id, found.connection_id, found.dataset, found.kind)
            self.enqueue_locked(conn, row, run_at=run_at,
                                queue=None if row.kind == RunKind.BACKFILL else queue)

    # -- workers -------------------------------------------------------------------------------

    def run_worker(self, *, queues: Sequence[str], until_idle: bool = False) -> None:
        """contract.Engine. Blocks. `until_idle` returns once no job is ready (tests, one-shot runs)."""
        options: dict[str, Any] = {"queues": list(queues), "wait": not until_idle}
        if until_idle:
            options["install_signal_handlers"] = False
        self.app.run_worker(**options)

    async def retry_stalled_jobs_async(self) -> list[int]:
        """Jobs still `doing` on a worker that stopped sending heartbeats (killed, OOM, host lost) go
        back to `todo`. Their runs' leases expire, so the next claim takes over with a new fence."""
        manager = self.app.job_manager
        stalled = await manager.get_stalled_jobs(seconds_since_heartbeat=STALLED_AFTER_S)
        retried = []
        for job in stalled:
            await manager.retry_job(job)
            if job.id is not None:
                retried.append(job.id)
        if retried:
            log.warning("retried %d stalled job(s): %s", len(retried), retried)
        return retried
