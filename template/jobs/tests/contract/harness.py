"""One object per implementation under test, so scenarios read the same whatever backs them.

`memory` wires the in-memory fakes; `postgres` wires PgLedger, PgCredentialStore, PgRateBudgets and
PgAuditSink on the real schema. Both share the synthetic providers, the fake clock, moto S3 and the
in-memory engine (the queue is exercised end to end separately, in test_end_to_end.py). A `Backend`
answers the questions scenarios ask that the contract protocols don't: published records, coverage, the
full run row, and seeding credentials.
"""

from __future__ import annotations

import json
import os
import random
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any, Protocol

from sqlalchemy import Engine, text

from jobs.storage import RawStore
from jobs.sync.contract import (
    ConnectionState,
    RunKind,
    RunSpec,
    RunStatus,
    RunView,
    Trigger,
    Window,
)
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
    AuditEvent,
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
MUTATIONS = frozenset({"heartbeat", "checkpoint", "save_raw", "publish", "complete", "wait", "fail"})


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
    """Wraps a ledger: counts the writes it accepted, logs waits, and can raise WorkerKilled right after
    the n-th successful call of one method."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.method: str | None = None
        self.on_call = 1
        self._count = 0
        self.writes = 0  # mutating calls after claim that the ledger accepted
        self.waits: list[tuple[uuid.UUID, str]] = []

    def arm(self, method: str, on_call: int = 1) -> None:
        self.method, self.on_call, self._count = method, on_call, 0

    def __getattr__(self, name: str) -> Any:
        target = getattr(self.inner, name)
        if not callable(target) or name.startswith("_"):
            return target

        def wrapped(*args: Any, **kwargs: Any) -> Any:
            result = target(*args, **kwargs)
            if name in MUTATIONS:
                self.writes += 1
            if name == "wait":
                self.waits.append((args[0].run_id, args[2]))
            if name == self.method:
                self._count += 1
                if self._count == self.on_call:
                    self.method = None
                    raise WorkerKilled(name)
            return result

        return wrapped


class RecordingBudgets:
    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self.blocks: list[tuple[str, datetime]] = []

    def blocked_until(self, budget_key: str) -> datetime | None:
        value: datetime | None = self.inner.blocked_until(budget_key)
        return value

    def block(self, budget_key: str, until: datetime) -> None:
        self.blocks.append((budget_key, until))
        self.inner.block(budget_key, until)


class Backend(Protocol):
    def records(self, connection_id: uuid.UUID, dataset: str) -> dict[str, Any]: ...
    def coverage(self, connection_id: uuid.UUID, dataset: str) -> tuple[Any, Any]: ...
    def run_row(self, run_id: uuid.UUID) -> Any: ...
    def running_runs(self) -> list[uuid.UUID]: ...
    def put_credential(self, connection_id: uuid.UUID, token: str, expires_at: datetime | None) -> None: ...
    def credential_version(self, connection_id: uuid.UUID) -> int: ...


# ---------------------------------------------------------------------------------------------
# Memory
# ---------------------------------------------------------------------------------------------


class MemoryBackend:
    def __init__(self, ledger: MemoryLedger, credentials: MemoryCredentialStore) -> None:
        self.ledger = ledger
        self.credentials = credentials

    def records(self, connection_id: uuid.UUID, dataset: str) -> dict[str, Any]:
        return dict(self.ledger.stream_records(connection_id, dataset))

    def coverage(self, connection_id: uuid.UUID, dataset: str) -> tuple[Any, Any]:
        return self.ledger.coverage(connection_id, dataset)

    def run_row(self, run_id: uuid.UUID) -> Any:
        return self.ledger.runs[run_id]

    def running_runs(self) -> list[uuid.UUID]:
        return [r.id for r in self.ledger.runs.values() if r.status is RunStatus.RUNNING]

    def put_credential(self, connection_id: uuid.UUID, token: str, expires_at: datetime | None) -> None:
        self.credentials.put(connection_id, token, expires_at)

    def credential_version(self, connection_id: uuid.UUID) -> int:
        return self.credentials.creds[connection_id].version


# ---------------------------------------------------------------------------------------------
# Postgres
# ---------------------------------------------------------------------------------------------


class PgConnections:
    """Operator actions on a connection (S3's routes do this in the backend): state plus an audit row."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def get(self, connection_id: uuid.UUID) -> ConnectionState:
        from jobs.sync.credentials import connection_state

        return connection_state(self.engine, connection_id)

    def set(self, connection_id: uuid.UUID, state: ConnectionState, reason: str | None = None,
            *, actor: str | None = None) -> None:
        with self.engine.begin() as conn:
            ws = conn.execute(text("update connections set state = :s, state_reason = :r, updated_at = now()"
                                   " where id = :id returning workspace_id"),
                              {"s": str(state), "r": reason, "id": connection_id}).scalar_one()
            conn.execute(text(
                "insert into audit_events (workspace_id, actor_type, actor_id, action, target_type, target_id)"
                " values (:ws, 'user', :actor, :action, 'connection', :target)"),
                {"ws": ws, "actor": actor or "operator", "action": f"connection.{state.value}",
                 "target": str(connection_id)})


class PgAudit:
    def __init__(self, engine: Engine) -> None:
        from jobs.sync.audit import PgAuditSink

        self.engine = engine
        self.sink = PgAuditSink(engine)

    def record(self, *args: Any, **kwargs: Any) -> None:
        self.sink.record(*args, **kwargs)

    @property
    def events(self) -> list[AuditEvent]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "select workspace_id, actor_type, actor_id, action, target_type, target_id, detail"
                " from audit_events order by id")).all()
        return [AuditEvent(r.workspace_id, r.actor_type, r.actor_id, r.action, r.target_type, r.target_id,
                           dict(r.detail)) for r in rows]


class PgBackend:
    def __init__(self, engine: Engine, vault: Any) -> None:
        self.engine = engine
        self.vault = vault

    def records(self, connection_id: uuid.UUID, dataset: str) -> dict[str, Any]:
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "select record_key, workspace_id, version, data, deleted, run_id, raw_object_id"
                " from synced_records where connection_id = :c and dataset = :d"),
                {"c": connection_id, "d": dataset}).all()
        return {r.record_key: SimpleNamespace(workspace_id=r.workspace_id, version=r.version, data=r.data,
                                              deleted=r.deleted, run_id=r.run_id,
                                              raw_object_id=r.raw_object_id) for r in rows}

    def coverage(self, connection_id: uuid.UUID, dataset: str) -> tuple[Any, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(text("select covered_from, covered_to from sync_streams"
                                    " where connection_id = :c and dataset = :d"),
                               {"c": connection_id, "d": dataset}).one_or_none()
        return (None, None) if row is None else (row.covered_from, row.covered_to)

    def run_row(self, run_id: uuid.UUID) -> Any:
        with self.engine.connect() as conn:
            r = conn.execute(text("select * from sync_runs where id = :id"), {"id": run_id}).one()
        receipt = r.receipt or {}
        return SimpleNamespace(**{**r._asdict(), "status": RunStatus(r.status),
                                  "deleted_inferred": int(receipt.get("deletions_inferred") or 0)})

    def running_runs(self) -> list[uuid.UUID]:
        with self.engine.connect() as conn:
            return list(conn.execute(text("select id from sync_runs where status = 'running'")).scalars())

    def put_credential(self, connection_id: uuid.UUID, token: str, expires_at: datetime | None) -> None:
        from jobs.sync.credentials import Secret

        blob = self.vault.seal(connection_id, Secret(access_token=token, extra={}))
        with self.engine.begin() as conn:
            conn.execute(text(
                "insert into credentials (connection_id, ciphertext, key_id, version, expires_at)"
                " values (:id, :blob, :key, 1, :exp) on conflict (connection_id) do update set"
                " ciphertext = excluded.ciphertext, key_id = excluded.key_id, version = 1,"
                " expires_at = excluded.expires_at, revoked_at = null"),
                {"id": connection_id, "blob": blob, "key": self.vault.key_id, "exp": expires_at})


    def credential_version(self, connection_id: uuid.UUID) -> int:
        with self.engine.connect() as conn:
            return int(conn.execute(text("select version from credentials where connection_id = :id"),
                                    {"id": connection_id}).scalar_one())


# ---------------------------------------------------------------------------------------------
# The harness
# ---------------------------------------------------------------------------------------------


@dataclass
class Harness:
    name: str
    clock: FakeClock
    ledger: Any
    credentials: Any
    connections: Any
    audit: Any
    budgets: RecordingBudgets
    raw_store: RawStore
    world: SyntheticWorld
    feed: SyntheticFeed
    report: SyntheticReportProvider
    kill: KillSwitch
    backend: Backend
    a: SyntheticAccount
    b: SyntheticAccount
    engine: MemoryEngine = field(init=False)
    seed: int = 7

    def __post_init__(self) -> None:
        self.engine = MemoryEngine(self.clock, self._waiting_until, lambda rid: execute(rid, self.deps()),
                                   max_steps=T.MAX_WORKER_STEPS_PER_SCENARIO)
        self._rng = random.Random(self.seed)  # noqa: S311 - jitter, not security

    def _waiting_until(self, run_id: uuid.UUID) -> datetime | None:
        row = self.backend.run_row(run_id)
        return row.next_attempt_at if row.status is RunStatus.WAITING else None

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

    def spec(self, account: SyntheticAccount | None = None, *, dataset: str = EVENTS,
             kind: RunKind = RunKind.INCREMENTAL, trigger: Trigger = Trigger.SCHEDULE,
             window: Window | None = None, version: str | None = None) -> RunSpec:
        account = account or self.a
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
        stalled = self.backend.running_runs()
        for run_id in stalled:
            self.engine.jobs = [j for j in self.engine.jobs if j.run_id != run_id]
            self.engine.enqueue(run_id)
        return stalled

    def put_credential(self, account: SyntheticAccount, token: str, expires_at: datetime | None) -> None:
        self.backend.put_credential(account.connection_id, token, expires_at)

    def credential_version(self, account: SyntheticAccount | None = None) -> int:
        return self.backend.credential_version((account or self.a).connection_id)

    # --- observing -------------------------------------------------------------------------------

    def run(self, run_id: uuid.UUID) -> RunView:
        view: RunView | None = self.ledger.get_run(run_id)
        assert view is not None
        return view

    def run_row(self, run_id: uuid.UUID) -> Any:
        return self.backend.run_row(run_id)

    def waits(self, run_id: uuid.UUID) -> list[str]:
        return [reason for rid, reason in self.kill.waits if rid == run_id]

    def records(self, account: SyntheticAccount | None = None, dataset: str = EVENTS) -> dict[str, Any]:
        return self.backend.records((account or self.a).connection_id, dataset)

    def coverage(self, account: SyntheticAccount | None = None, dataset: str = EVENTS) -> tuple[Any, Any]:
        return self.backend.coverage((account or self.a).connection_id, dataset)

    @property
    def provider_calls(self) -> int:
        return self.feed.call_count + self.report.call_count


def _world(clock: FakeClock) -> SyntheticWorld:
    return SyntheticWorld(on_call=lambda: clock.advance(T.PROVIDER_LATENCY_S))


def memory_harness(s3_client: Any, bucket: str) -> Harness:
    clock = FakeClock(START + 2 * DAY)
    audit = MemoryAudit()
    connections = MemoryConnections(audit)
    credentials = MemoryCredentialStore(connections, audit)
    ledger = MemoryLedger(clock)
    world = _world(clock)
    for account in SYNTHETIC_WORKSPACES:
        connections.add(account.connection_id, account.workspace_id)
        token = f"tok-{account.label}-0"
        credentials.put(account.connection_id, token)
        world.grant(account.connection_id, token)
    a, b = SYNTHETIC_WORKSPACES
    return Harness(name="memory", clock=clock, ledger=ledger, credentials=credentials,
                   connections=connections, audit=audit, budgets=RecordingBudgets(MemoryBudgets()),
                   raw_store=RawStore(bucket, s3_client), world=world, feed=SyntheticFeed(world),
                   report=SyntheticReportProvider(world), kill=KillSwitch(ledger),
                   backend=MemoryBackend(ledger, credentials), a=a, b=b)


def postgres_harness(engine: Engine, workspaces: tuple[str, str], s3_client: Any, bucket: str) -> Harness:
    from jobs.sync.budgets import PgRateBudgets
    from jobs.sync.credentials import LocalKeyWrapper, PgCredentialStore, Vault
    from jobs.sync.ledger import PgLedger

    clock = FakeClock(START + 2 * DAY)
    vault = Vault(LocalKeyWrapper(os.urandom(32)))
    backend = PgBackend(engine, vault)
    world = _world(clock)
    accounts = []
    for label, ws in zip(("a", "b"), workspaces, strict=True):
        account = SyntheticAccount(label=label, workspace_id=uuid.UUID(ws), connection_id=uuid.uuid4(),
                                   account_ref=f"acct-{label}")
        with engine.begin() as conn:
            conn.execute(text(
                "insert into connections (id, workspace_id, provider, account_ref, display_name, config)"
                " values (:id, :ws, 'synthetic-feed', :ref, :name, cast(:config as jsonb))"),
                {"id": account.connection_id, "ws": account.workspace_id, "ref": account.account_ref,
                 "name": f"Synthetic {label}", "config": json.dumps({})})
        token = f"tok-{label}-0"
        backend.put_credential(account.connection_id, token, None)
        world.grant(account.connection_id, token)
        accounts.append(account)
    ledger = PgLedger(engine, clock=clock.now)
    return Harness(name="postgres", clock=clock, ledger=ledger, credentials=PgCredentialStore(engine, vault),
                   connections=PgConnections(engine), audit=PgAudit(engine),
                   budgets=RecordingBudgets(PgRateBudgets(engine)), raw_store=RawStore(bucket, s3_client),
                   world=world, feed=SyntheticFeed(world), report=SyntheticReportProvider(world),
                   kill=KillSwitch(ledger), backend=backend, a=accounts[0], b=accounts[1])
