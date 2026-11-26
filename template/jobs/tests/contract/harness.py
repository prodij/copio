"""One object per implementation under test, so scenarios read the same whatever backs them.

`memory` wires the in-memory fakes. The integrator adds `postgres` in conftest.py: a Harness whose
ledger, credentials, connections and audit are the Postgres implementations and whose observation
helpers (`records`, `coverage`, `run_row`, `audit_events`) read the tables.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from jobs.storage import RawStore
from jobs.sync.contract import RunKind, RunSpec, RunView, Trigger, Window
from jobs.sync.runner import AnyProvider, Outcome, RunnerDeps, RunnerPolicy, execute
from jobs.sync.testing import (
    SYNTHETIC_WORKSPACES,
    SyntheticAccount,
    SyntheticFeed,
    SyntheticReportProvider,
    SyntheticWorld,
)
from jobs.sync.testing.world import EVENTS, SNAPSHOT_DATASETS

from . import thresholds as T
from .fakes import (
    FakeClock,
    MemoryAudit,
    MemoryBudgets,
    MemoryConnections,
    MemoryCredentialStore,
    MemoryEngine,
    MemoryLedger,
)

START = datetime(2026, 11, 1, tzinfo=UTC)
DAY = timedelta(days=1)
A, B = SYNTHETIC_WORKSPACES


class WorkerKilled(BaseException):
    """The process died. BaseException, so nothing in the runner can swallow it."""


def policy() -> RunnerPolicy:
    return RunnerPolicy(
        lease_s=T.LEASE_S, heartbeat_fraction=T.HEARTBEAT_FRACTION,
        backfill_pages_per_claim=T.BACKFILL_PAGES_PER_CLAIM,
        report_poll_interval_s=T.REPORT_POLL_INTERVAL_S, max_report_polls=T.MAX_REPORT_POLLS,
        max_rate_limit_waits=T.MAX_RATE_LIMIT_WAITS, rate_limit_default_s=T.RATE_LIMIT_DEFAULT_S,
        rate_limit_jitter_fraction=T.RATE_LIMIT_JITTER_FRACTION, retry_base_s=T.RETRY_BASE_S,
        retry_cap_s=T.RETRY_CAP_S, min_retry_delay_s=T.MIN_RETRY_DELAY_S,
        max_claims_per_run=T.MAX_CLAIMS_PER_RUN, pause_recheck_s=T.PAUSE_RECHECK_S,
        snapshot_datasets=SNAPSHOT_DATASETS)


class KillSwitch:
    """Wraps a ledger; raises WorkerKilled right after the n-th successful call of `method`."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.method: str | None = None
        self.on_call = 1
        self._count = 0

    def arm(self, method: str, on_call: int = 1) -> None:
        self.method, self.on_call, self._count = method, on_call, 0

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.inner, name)
        if name != self.method:
            return target

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            result = target(*args, **kwargs)
            self._count += 1
            if self._count == self.on_call:
                self.method = None
                raise WorkerKilled(name)
            return result

        return wrapped


@dataclass
class Harness:
    name: str
    clock: FakeClock
    ledger: MemoryLedger
    credentials: MemoryCredentialStore
    connections: MemoryConnections
    audit: MemoryAudit
    budgets: MemoryBudgets
    raw_store: RawStore
    world: SyntheticWorld
    feed: SyntheticFeed
    report: SyntheticReportProvider
    kill: KillSwitch
    engine: MemoryEngine = field(init=False)
    seed: int = 7

    def __post_init__(self) -> None:
        self.engine = MemoryEngine(self.clock, self.ledger, lambda rid: execute(rid, self.deps()),
                                   max_steps=T.MAX_WORKER_STEPS_PER_SCENARIO)
        self._rng = random.Random(self.seed)  # noqa: S311 - jitter, not security

    # --- wiring ----------------------------------------------------------------------------------

    def provider_for(self, spec: RunSpec) -> AnyProvider:
        return self.report if spec.kind is RunKind.REPORT else self.feed

    def deps(self, owner: str = "worker-1", providers: Callable[[RunSpec], AnyProvider] | None = None,
             ) -> RunnerDeps:
        return RunnerDeps(ledger=self.kill, credentials=self.credentials, raw_store=self.raw_store,
                          providers=providers or self.provider_for, budgets=self.budgets,
                          audit=self.audit, connection_state=self.connections.get, clock=self.clock,
                          owner=owner, policy=policy(), rng=self._rng)

    # --- driving ---------------------------------------------------------------------------------

    def spec(self, account: SyntheticAccount = A, *, dataset: str = EVENTS,
             kind: RunKind = RunKind.INCREMENTAL, trigger: Trigger = Trigger.SCHEDULE,
             window: Window | None = None, version: str | None = None) -> RunSpec:
        return RunSpec(workspace_id=account.workspace_id, connection_id=account.connection_id,
                       dataset=dataset, kind=kind, trigger=trigger,
                       window=window or Window(START, START + DAY),
                       connector_version=version or self.feed.version)

    def submit(self, spec: RunSpec) -> uuid.UUID:
        """What a schedule, webhook or operator does: an outbox row, then the dispatcher enqueues."""
        run_id, _ = self.ledger.create_run(spec)
        self.engine.enqueue(run_id, queue="backfill" if spec.kind is RunKind.BACKFILL else "sync")
        return run_id

    def drain(self) -> None:
        self.engine.run_worker(queues=("sync", "backfill"), until_idle=True)

    def once(self, run_id: uuid.UUID, owner: str = "worker-1") -> Outcome:
        return execute(run_id, self.deps(owner))

    def recover_stalled(self) -> list[uuid.UUID]:
        """S2's stalled-job recovery: after the lease expires, re-enqueue runs a dead worker held."""
        self.clock.advance(T.LEASE_S + 1)
        stalled = [r.id for r in self.ledger.runs.values() if r.status.value == "running"]
        for run_id in stalled:
            self.engine.jobs = [j for j in self.engine.jobs if j.run_id != run_id]
            self.engine.enqueue(run_id)
        return stalled

    # --- observing -------------------------------------------------------------------------------

    def run(self, run_id: uuid.UUID) -> RunView:
        view = self.ledger.get_run(run_id)
        assert view is not None
        return view

    def run_row(self, run_id: uuid.UUID) -> Any:
        return self.ledger.runs[run_id]

    def records(self, account: SyntheticAccount = A, dataset: str = EVENTS) -> dict[str, Any]:
        return self.ledger.stream_records(account.connection_id, dataset)

    def coverage(self, account: SyntheticAccount = A, dataset: str = EVENTS) -> tuple[Any, Any]:
        return self.ledger.coverage(account.connection_id, dataset)

    @property
    def provider_calls(self) -> int:
        return self.feed.call_count + self.report.call_count


def memory_harness(s3_client: Any, bucket: str) -> Harness:
    clock = FakeClock(START + 2 * DAY)
    audit = MemoryAudit()
    connections = MemoryConnections(audit)
    credentials = MemoryCredentialStore(connections, audit)
    ledger = MemoryLedger(clock)
    world = SyntheticWorld(on_call=lambda: clock.advance(T.PROVIDER_LATENCY_S))
    for account in SYNTHETIC_WORKSPACES:
        connections.add(account.connection_id, account.workspace_id)
        token = f"tok-{account.label}-0"
        credentials.put(account.connection_id, token)
        world.grant(account.connection_id, token)
    return Harness(name="memory", clock=clock, ledger=ledger, credentials=credentials,
                   connections=connections, audit=audit, budgets=MemoryBudgets(),
                   raw_store=RawStore(bucket, s3_client), world=world, feed=SyntheticFeed(world),
                   report=SyntheticReportProvider(world), kill=KillSwitch(ledger))


