"""In-memory Ledger, CredentialStore and Engine: an executable spec of the semantics S1, S2 and S3 build.

Read this alongside contract.py. Where the protocol docstrings are silent, the choice made here is
written down next to the code ("Semantics:"), and the Postgres implementations must match it, because
the contract suite runs against both.
"""

from __future__ import annotations

import heapq
import itertools
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from jobs.sync.contract import (
    ConnectionState,
    Credential,
    Lease,
    PublishResult,
    RawObjectView,
    Record,
    RunKind,
    RunSpec,
    RunStatus,
    RunView,
    Stage,
    StaleLease,
    TokenRefresher,
    Window,
)
from jobs.sync.runner import Outcome

TERMINAL = {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}


class FakeClock:
    def __init__(self, start: datetime) -> None:
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)

    def set(self, when: datetime) -> None:
        if when > self._now:
            self._now = when


class BacklogNotEmpty(Exception):
    """complete() was called while raw objects of the run were unpublished."""


class IntegrityError(Exception):
    """Stands in for a unique-constraint violation in Postgres."""


@dataclass
class _Run:
    id: uuid.UUID
    spec: RunSpec
    status: RunStatus = RunStatus.QUEUED
    stage: Stage = Stage.PENDING
    checkpoint: dict[str, Any] = field(default_factory=dict)
    attempt: int = 0
    max_attempts: int = 5
    replay_of: uuid.UUID | None = None
    next_attempt_at: datetime | None = None
    wait_reason: str | None = None
    error_code: str | None = None
    error_detail: str | None = None
    provider_request_ref: str | None = None
    records_accepted: int = 0
    records_rejected: int = 0
    records_stale: int = 0
    deleted_inferred: int = 0
    seen_keys: set[str] = field(default_factory=set)
    waits: list[str] = field(default_factory=list)


@dataclass
class _Stream:
    workspace_id: uuid.UUID
    fence: int = 0
    lease_run_id: uuid.UUID | None = None
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    covered_from: datetime | None = None
    covered_to: datetime | None = None
    last_publish_at: datetime | None = None
    last_publish_run_id: uuid.UUID | None = None


@dataclass
class _Raw:
    id: uuid.UUID
    run_id: uuid.UUID
    connection_id: uuid.UUID
    dataset: str
    page_seq: int
    storage_key: str
    sha256: str
    size: int
    processed_at: datetime | None = None


@dataclass
class StoredRecord:
    workspace_id: uuid.UUID
    version: str
    data: Mapping[str, Any]
    deleted: bool
    run_id: uuid.UUID
    raw_object_id: uuid.UUID | None


class MemoryLedger:
    """Implements `Ledger`."""

    def __init__(self, clock: FakeClock) -> None:
        self.clock = clock
        self.runs: dict[uuid.UUID, _Run] = {}
        self.by_dedupe: dict[str, uuid.UUID] = {}
        self.streams: dict[tuple[uuid.UUID, str], _Stream] = {}
        self.raw: dict[uuid.UUID, _Raw] = {}
        self.records: dict[tuple[uuid.UUID, str, str], StoredRecord] = {}
        self.writes = 0  # every successful mutation after claim; a stale lease must not move this

    # --- runs ------------------------------------------------------------------------------------

    def create_run(self, spec: RunSpec) -> tuple[uuid.UUID, bool]:
        """Semantics: idempotent by dedupe key, whatever the existing run's status."""
        key = spec.dedupe_key()
        if key in self.by_dedupe:
            return self.by_dedupe[key], False
        run_id = uuid.uuid4()
        self.runs[run_id] = _Run(run_id, spec)
        self.by_dedupe[key] = run_id
        self.streams.setdefault((spec.connection_id, spec.dataset), _Stream(spec.workspace_id))
        return run_id, True

    def create_replay(self, source_run_id: uuid.UUID, connector_version: str,
                      requested_by: str | None = None) -> uuid.UUID:
        """Semantics: a new queued run of kind REPLAY with `replay_of` set, the source run's window, and a
        dedupe key of its own, so each replay request is a separate run."""
        source = self.runs[source_run_id]
        spec = replace(source.spec, kind=RunKind.REPLAY, connector_version=connector_version)
        run_id = uuid.uuid4()
        self.runs[run_id] = _Run(run_id, spec, replay_of=source_run_id)
        self.by_dedupe[f"replay:{run_id}"] = run_id
        return run_id

    def get_run(self, run_id: uuid.UUID) -> RunView | None:
        run = self.runs.get(run_id)
        if run is None:
            return None
        return RunView(run_id=run.id, spec=run.spec, status=run.status, stage=run.stage,
                       checkpoint=dict(run.checkpoint), attempt=run.attempt,
                       max_attempts=run.max_attempts, replay_of=run.replay_of)

    def raw_objects(self, run_id: uuid.UUID) -> Sequence[RawObjectView]:
        """Semantics: ordered by page_seq."""
        rows = sorted((r for r in self.raw.values() if r.run_id == run_id), key=lambda r: r.page_seq)
        return [RawObjectView(id=r.id, run_id=r.run_id, page_seq=r.page_seq, storage_key=r.storage_key,
                              sha256=r.sha256, size=r.size, processed=r.processed_at is not None)
                for r in rows]

    # --- leases ----------------------------------------------------------------------------------

    def claim(self, run_id: uuid.UUID, owner: str, lease_s: float) -> Lease | None:
        """Semantics: None for a terminal run or while any live lease holds the stream (even one of the
        same run: that is a duplicate execution). Otherwise the fence goes up by one, the run becomes
        running, and `attempt` goes up by one, so duplicate and crashed attempts stay visible."""
        run = self.runs[run_id]
        if run.status in TERMINAL:
            return None
        stream = self.streams.setdefault((run.spec.connection_id, run.spec.dataset),
                                         _Stream(run.spec.workspace_id))
        now = self.clock.now()
        if stream.lease_expires_at is not None and stream.lease_expires_at > now:
            return None
        stream.fence += 1
        stream.lease_run_id = run_id
        stream.lease_owner = owner
        stream.lease_expires_at = now + timedelta(seconds=lease_s)
        run.status = RunStatus.RUNNING
        run.attempt += 1
        run.next_attempt_at = None
        run.wait_reason = None
        return Lease(run_id=run_id, connection_id=run.spec.connection_id, dataset=run.spec.dataset,
                     owner=owner, fence=stream.fence, expires_at=stream.lease_expires_at)

    def _check(self, lease: Lease) -> tuple[_Run, _Stream]:
        """Semantics: a write is fenced by (fence, run id). An expired lease nobody has taken over is still
        valid; a released lease (after wait, fail or complete) is not."""
        stream = self.streams[(lease.connection_id, lease.dataset)]
        if stream.fence != lease.fence or stream.lease_run_id != lease.run_id:
            raise StaleLease(str(lease.run_id))
        return self.runs[lease.run_id], stream

    def heartbeat(self, lease: Lease, lease_s: float) -> Lease:
        _, stream = self._check(lease)
        stream.lease_expires_at = self.clock.now() + timedelta(seconds=lease_s)
        self.writes += 1
        return replace(lease, expires_at=stream.lease_expires_at)

    def _release(self, stream: _Stream) -> None:
        stream.lease_run_id = None
        stream.lease_owner = None
        stream.lease_expires_at = None

    # --- progress --------------------------------------------------------------------------------

    def checkpoint(self, lease: Lease, stage: Stage, data: Mapping[str, Any]) -> None:
        """Semantics: replaces the whole checkpoint (the runner always writes all of it)."""
        run, _ = self._check(lease)
        run.stage = stage
        run.checkpoint = dict(data)
        self.writes += 1

    def save_raw(self, lease: Lease, page_seq: int, storage_key: str, sha256: str, size: int) -> uuid.UUID:
        run, _ = self._check(lease)
        for r in self.raw.values():
            if (r.run_id == run.id and r.page_seq == page_seq) or r.storage_key == storage_key:
                raise IntegrityError("raw object already recorded")
        raw_id = uuid.uuid4()
        self.raw[raw_id] = _Raw(raw_id, run.id, run.spec.connection_id, run.spec.dataset, page_seq,
                                storage_key, sha256, size)
        self.writes += 1
        return raw_id

    def publish(self, lease: Lease, raw_object_id: uuid.UUID, records: Sequence[Record]) -> PublishResult:
        """Semantics: per record, newer version wins; an equal version replaces (a replay re-derives the
        same version from the same raw); an older version is skipped and counted stale. A record with an
        empty key or version is rejected. The raw object may belong to another run of the same stream
        (replay). Marks the raw object processed. All or nothing."""
        run, stream = self._check(lease)
        raw = self.raw[raw_object_id]
        if (raw.connection_id, raw.dataset) != (run.spec.connection_id, run.spec.dataset):
            raise ValueError("raw object belongs to another stream")
        accepted = rejected = stale = 0
        for rec in records:
            if not rec.key or not rec.version:
                rejected += 1
                continue
            run.seen_keys.add(rec.key)
            ident = (run.spec.connection_id, run.spec.dataset, rec.key)
            current = self.records.get(ident)
            if current is not None and current.version > rec.version:
                stale += 1
                continue
            self.records[ident] = StoredRecord(run.spec.workspace_id, rec.version, dict(rec.data),
                                               rec.deleted, run.id, raw_object_id)
            accepted += 1
        raw.processed_at = self.clock.now()
        run.records_accepted += accepted
        run.records_rejected += rejected
        run.records_stale += stale
        stream.last_publish_at = self.clock.now()
        stream.last_publish_run_id = run.id
        self.writes += 1
        return PublishResult(accepted=accepted, rejected=rejected, stale_skipped=stale)

    def complete(self, lease: Lease, window: Window, snapshot_complete: bool) -> None:
        """Semantics: raises BacklogNotEmpty (and changes nothing) if a raw object of the run is
        unprocessed. Coverage is one contiguous range; a window that overlaps or touches it extends it, a
        window with a gap leaves it alone. With snapshot_complete, every live record of the stream this
        run did not see is marked deleted. The run succeeds and the lease is released."""
        run, stream = self._check(lease)
        if any(r.run_id == run.id and r.processed_at is None for r in self.raw.values()):
            raise BacklogNotEmpty(str(run.id))
        if stream.covered_from is None or stream.covered_to is None:
            stream.covered_from, stream.covered_to = window.start, window.end
        elif window.start <= stream.covered_to and window.end >= stream.covered_from:
            stream.covered_from = min(stream.covered_from, window.start)
            stream.covered_to = max(stream.covered_to, window.end)
        if snapshot_complete:
            for (conn, ds, key), rec in self.records.items():
                if (conn, ds) == (run.spec.connection_id, run.spec.dataset) and not rec.deleted \
                        and key not in run.seen_keys:
                    rec.deleted = True
                    run.deleted_inferred += 1
        run.status = RunStatus.SUCCEEDED
        run.stage = Stage.PUBLISHED
        self._release(stream)
        self.writes += 1

    def wait(self, lease: Lease, until: datetime, reason: str) -> None:
        """Semantics: status waiting with next_attempt_at; the lease is released (the fence stays)."""
        run, stream = self._check(lease)
        run.status = RunStatus.WAITING
        run.next_attempt_at = until
        run.wait_reason = reason
        run.waits.append(reason)
        self._release(stream)
        self.writes += 1

    def fail(self, lease: Lease, error_code: str, detail: str, request_ref: str | None) -> None:
        run, stream = self._check(lease)
        run.status = RunStatus.FAILED
        run.error_code = error_code
        run.error_detail = detail
        run.provider_request_ref = request_ref
        self._release(stream)
        self.writes += 1

    # --- observation (what the contract suite reads) ---------------------------------------------

    def coverage(self, connection_id: uuid.UUID, dataset: str) -> tuple[datetime | None, datetime | None]:
        stream = self.streams.get((connection_id, dataset))
        return (stream.covered_from, stream.covered_to) if stream else (None, None)

    def stream_records(self, connection_id: uuid.UUID, dataset: str) -> dict[str, StoredRecord]:
        return {key: rec for (conn, ds, key), rec in self.records.items()
                if (conn, ds) == (connection_id, dataset)}


# ---------------------------------------------------------------------------------------------
# Connections, audit, budgets
# ---------------------------------------------------------------------------------------------


@dataclass
class AuditEvent:
    workspace_id: uuid.UUID
    actor_type: str
    actor_id: str
    action: str
    target_type: str
    target_id: str
    detail: Mapping[str, Any]


class MemoryAudit:
    """Append-only, like audit_events."""

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, workspace_id: uuid.UUID, action: str, target_type: str, target_id: str,
               detail: Mapping[str, Any]) -> None:
        self.events.append(AuditEvent(workspace_id, "system", "sync-runner", action, target_type,
                                      target_id, dict(detail)))

    def operator(self, workspace_id: uuid.UUID, user: str, action: str, target_type: str,
                 target_id: str, detail: Mapping[str, Any] | None = None) -> None:
        self.events.append(AuditEvent(workspace_id, "user", user, action, target_type, target_id,
                                      dict(detail or {})))


class MemoryConnections:
    def __init__(self, audit: MemoryAudit) -> None:
        self.audit = audit
        self.state: dict[uuid.UUID, ConnectionState] = {}
        self.reason: dict[uuid.UUID, str | None] = {}
        self.workspace: dict[uuid.UUID, uuid.UUID] = {}

    def add(self, connection_id: uuid.UUID, workspace_id: uuid.UUID) -> None:
        self.state[connection_id] = ConnectionState.HEALTHY
        self.workspace[connection_id] = workspace_id

    def get(self, connection_id: uuid.UUID) -> ConnectionState:
        return self.state[connection_id]

    def set(self, connection_id: uuid.UUID, state: ConnectionState, reason: str | None = None,
            *, actor: str | None = None) -> None:
        """An operator action (S3's routes), audited as a user."""
        self.state[connection_id] = state
        self.reason[connection_id] = reason
        self.audit.operator(self.workspace[connection_id], actor or "operator",
                            f"connection.{state.value}", "connection", str(connection_id))


class MemoryCredentialStore:
    """Implements `CredentialStore`.

    Semantics: `rotate` saves only if cred.version is current and returns the stored credential with
    version + 1; otherwise it saves nothing and returns the newer stored credential. `refresh` does the
    same around one provider call, holding the per-connection lock (trivially held here: one thread):
    if cred.version is stale it returns the stored credential without calling the provider; AuthRevoked
    from the provider propagates and nothing is saved. `mark_revoked` moves the connection to
    reconnect_needed and writes a system audit event in the same step."""

    def __init__(self, connections: MemoryConnections, audit: MemoryAudit) -> None:
        self.connections = connections
        self.audit = audit
        self.creds: dict[uuid.UUID, Credential] = {}
        self.rotations = 0
        self.lost_races = 0
        self.provider_refreshes = 0

    def put(self, connection_id: uuid.UUID, token: str, expires_at: datetime | None = None) -> None:
        self.creds[connection_id] = Credential(connection_id, token, 1, expires_at)

    def get(self, connection_id: uuid.UUID) -> Credential:
        return self.creds[connection_id]

    def rotate(self, cred: Credential, access_token: str, expires_at: datetime | None,
               extra: Mapping[str, str] | None = None) -> Credential:
        current = self.creds[cred.connection_id]
        if current.version != cred.version:
            self.lost_races += 1
            return current
        new = Credential(cred.connection_id, access_token, current.version + 1, expires_at,
                         dict(extra) if extra is not None else dict(current.extra))
        self.creds[cred.connection_id] = new
        self.rotations += 1
        return new

    def refresh(self, cred: Credential, refresher: TokenRefresher) -> Credential:
        current = self.creds[cred.connection_id]
        if current.version != cred.version:
            self.lost_races += 1
            return current
        self.provider_refreshes += 1
        token, expires_at = refresher.refresh_token(current)
        return self.rotate(current, token, expires_at)

    def mark_revoked(self, connection_id: uuid.UUID, reason: str) -> None:
        self.connections.state[connection_id] = ConnectionState.RECONNECT_NEEDED
        self.connections.reason[connection_id] = reason
        self.audit.record(self.connections.workspace[connection_id], "connection.reconnect_needed",
                          "connection", str(connection_id), {"reason": reason})


class MemoryBudgets:
    def __init__(self) -> None:
        self.blocked: dict[str, datetime] = {}
        self.blocks: list[tuple[str, datetime]] = []

    def blocked_until(self, budget_key: str) -> datetime | None:
        return self.blocked.get(budget_key)

    def block(self, budget_key: str, until: datetime) -> None:
        """Semantics: blocked_until only moves later."""
        self.blocks.append((budget_key, until))
        if budget_key not in self.blocked or until > self.blocked[budget_key]:
            self.blocked[budget_key] = until


# ---------------------------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------------------------


class BusyLoop(Exception):
    """The worker ran more executions than the scenario allows."""


@dataclass(order=True)
class _Job:
    run_at: datetime
    priority: int
    seq: int
    run_id: uuid.UUID = field(compare=False)
    queue: str = field(compare=False)


@dataclass
class Execution:
    at: datetime
    run_id: uuid.UUID
    queue: str
    outcome: Outcome
    finished_at: datetime


class MemoryEngine:
    """Implements `Engine` with one worker on a virtual clock.

    Semantics: jobs carry a run id only. A worker takes the earliest due job, preferring queues in the
    order given to run_worker (so "sync" before "backfill" when both are due). After an execution it
    plays the dispatcher's part: a run left waiting is enqueued again at next_attempt_at, a run that
    found its stream busy is retried after `busy_retry_s`. With until_idle, when nothing is due the
    clock jumps to the next job; the worker stops when the queues are empty."""

    def __init__(self, clock: FakeClock, ledger: MemoryLedger,
                 task: Callable[[uuid.UUID], Outcome], *, max_steps: int, busy_retry_s: float = 5.0) -> None:
        self.clock = clock
        self.ledger = ledger
        self.task = task
        self.max_steps = max_steps
        self.busy_retry_s = busy_retry_s
        self.jobs: list[_Job] = []
        self.history: list[Execution] = []
        self._seq = itertools.count()

    def enqueue(self, run_id: uuid.UUID, *, run_at: datetime | None = None, queue: str = "sync") -> None:
        heapq.heappush(self.jobs, _Job(run_at or self.clock.now(), 0, next(self._seq), run_id, queue))

    def _take(self, queues: Sequence[str]) -> _Job | None:
        now = self.clock.now()
        due = [j for j in self.jobs if j.run_at <= now and j.queue in queues]
        if not due:
            return None
        due.sort(key=lambda j: (queues.index(j.queue), j.run_at, j.seq))
        job = due[0]
        self.jobs.remove(job)
        heapq.heapify(self.jobs)
        return job

    def run_worker(self, *, queues: Sequence[str], until_idle: bool = False) -> None:
        while True:
            job = self._take(queues)
            if job is None:
                pending = [j for j in self.jobs if j.queue in queues]
                if not until_idle or not pending:
                    return
                self.clock.set(min(j.run_at for j in pending))
                continue
            self.step(job)

    def run_steps(self, n: int, *, queues: Sequence[str] = ("sync", "backfill")) -> None:
        """Run at most n executions, jumping the clock to the next job when nothing is due."""
        for _ in range(n):
            job = self._take(queues)
            if job is None:
                pending = [j for j in self.jobs if j.queue in queues]
                if not pending:
                    return
                self.clock.set(min(j.run_at for j in pending))
                job = self._take(queues)
                assert job is not None
            self.step(job)

    def step(self, job: _Job) -> Outcome:
        if len(self.history) >= self.max_steps:
            raise BusyLoop(f"more than {self.max_steps} executions")
        at = self.clock.now()
        outcome = self.task(job.run_id)
        self.history.append(Execution(at, job.run_id, job.queue, outcome, self.clock.now()))
        run = self.ledger.runs[job.run_id]
        if run.status is RunStatus.WAITING and run.next_attempt_at is not None:
            self.enqueue(job.run_id, run_at=run.next_attempt_at, queue=job.queue)
        elif outcome is Outcome.BUSY:
            self.enqueue(job.run_id, run_at=at + timedelta(seconds=self.busy_retry_s), queue=job.queue)
        return outcome
