"""The connector layer's shared contract. Every part of the layer codes against these types.

Spec: docs/superpowers/specs/2026-11-25-connector-layer-design.md (in the template repo).

Generic, for every product: providers, runs, leases, checkpoints, publishing, coverage.
Product-specific (generated product, never here): real provider adapters, metrics, what a dataset means.

Changing this file changes every session's work. Only the integrator edits it; a session that needs a
change says so in its report instead.
"""

from __future__ import annotations

import enum
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------------------------
# Vocabulary (the string values are stored in Postgres; see migration 0004)
# ---------------------------------------------------------------------------------------------


class ConnectionState(enum.StrEnum):
    HEALTHY = "healthy"
    RECONNECT_NEEDED = "reconnect_needed"  # auth revoked or refresh failed for good: no new runs
    PAUSED = "paused"  # an operator paused future syncs; running work finishes its current unit
    DISCONNECTED = "disconnected"


class RunKind(enum.StrEnum):
    INCREMENTAL = "incremental"
    BACKFILL = "backfill"
    REPORT = "report"  # asynchronous report lifecycle (request, poll, download)
    REPLAY = "replay"  # re-process stored raw objects; never calls the provider


class Trigger(enum.StrEnum):
    SCHEDULE = "schedule"
    WEBHOOK = "webhook"
    MANUAL = "manual"
    RETRY = "retry"


class RunStatus(enum.StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING = "waiting"  # yielded: rate limit, or a report still processing. Has next_attempt_at
    SUCCEEDED = "succeeded"
    FAILED = "failed"  # terminal after bounded attempts; needs an operator or a new trigger
    CANCELLED = "cancelled"


class Stage(enum.StrEnum):
    """Where a run is. Fetch progress and publish progress are separate on purpose."""

    PENDING = "pending"
    REQUESTED = "requested"  # report requested; checkpoint holds the provider's report id
    FETCHING = "fetching"
    FETCHED = "fetched"  # every raw object saved; publishing not finished
    PUBLISHED = "published"


class ReportState(enum.StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    DONE = "done"
    CANCELLED_NO_DATA = "cancelled_no_data"  # a legitimate empty result, not a failure
    FATAL = "fatal"


# ---------------------------------------------------------------------------------------------
# Provider errors: a provider raises these, the runner decides what happens next
# ---------------------------------------------------------------------------------------------


class ProviderError(Exception):
    """Base. `request_ref` is the provider's request id, safe to show an operator. `raw` is the response
    body when the provider got one it could not use (a schema change): the runner stores it for replay.
    The message is never shown to an operator; the runner records a fixed code instead."""

    def __init__(self, message: str, *, request_ref: str | None = None, raw: bytes | None = None) -> None:
        super().__init__(message)
        self.request_ref = request_ref
        self.raw = raw


class RateLimited(ProviderError):
    def __init__(self, message: str, *, retry_after_s: float | None, budget_key: str,
                 request_ref: str | None = None) -> None:
        super().__init__(message, request_ref=request_ref)
        self.retry_after_s = retry_after_s
        self.budget_key = budget_key


class TransientError(ProviderError):
    """Timeouts, 5xx: retry with backoff and jitter, up to the bounded attempt count."""


class AuthRevoked(ProviderError):
    """Credentials no longer work. The connection moves to reconnect_needed; no blind retries."""


class PermanentError(ProviderError):
    """A request that will never succeed as sent (400, schema change). Fails the run unit."""


# ---------------------------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Window:
    """Half-open [start, end) in UTC."""

    start: datetime
    end: datetime


@dataclass(frozen=True)
class Record:
    """One provider object at one version. `version` must order newer-after-older for this dataset
    (an updated_at timestamp, a sequence number). Publishing never replaces a newer version with an
    older one, which is how a stale poll loses to a newer webhook."""

    key: str
    version: str
    data: Mapping[str, Any]
    deleted: bool = False


@dataclass(frozen=True)
class Page:
    records: Sequence[Record]
    next_cursor: str | None  # None: this window is complete
    raw: bytes  # the exact response body, saved before anything parses it
    raw_ext: str = "json"
    request_ref: str | None = None
    complete_snapshot: bool = False  # True only if the provider guarantees this is the full set


@dataclass(frozen=True)
class ReportStatus:
    state: ReportState
    document_ref: str | None = None
    request_ref: str | None = None


@dataclass(frozen=True)
class Credential:
    """Decrypted, in memory, inside a worker only. Never logged, queued, or returned by an API."""

    connection_id: uuid.UUID
    access_token: str
    version: int  # optimistic-concurrency version for rotation
    expires_at: datetime | None = None
    extra: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RunSpec:
    """What a run is for. Stored on sync_runs; the queue carries only the run id."""

    workspace_id: uuid.UUID
    connection_id: uuid.UUID
    dataset: str
    kind: RunKind
    trigger: Trigger
    window: Window
    connector_version: str

    def dedupe_key(self) -> str:
        """Two triggers for the same unit of work produce one run."""
        return (f"{self.connection_id}:{self.dataset}:{self.kind}:"
                f"{self.window.start.isoformat()}:{self.window.end.isoformat()}")


@dataclass(frozen=True)
class Lease:
    """Ownership of one (connection, dataset) stream. `fence` increases on every new claim; the ledger
    refuses checkpoint and publish calls that carry an older fence."""

    run_id: uuid.UUID
    connection_id: uuid.UUID
    dataset: str
    owner: str
    fence: int
    expires_at: datetime


@dataclass(frozen=True)
class RunView:
    """A read of one sync_runs row."""

    run_id: uuid.UUID
    spec: RunSpec
    status: RunStatus
    stage: Stage
    checkpoint: Mapping[str, Any]
    attempt: int  # claims so far: claim increments it
    max_attempts: int
    replay_of: uuid.UUID | None = None


@dataclass(frozen=True)
class RawObjectView:
    """A read of one raw_objects row."""

    id: uuid.UUID
    run_id: uuid.UUID
    page_seq: int
    storage_key: str
    sha256: str
    size: int
    processed: bool


@dataclass(frozen=True)
class PublishResult:
    accepted: int
    rejected: int
    stale_skipped: int  # older versions that lost to what was already published


# ---------------------------------------------------------------------------------------------
# Ports: implementations live in jobs/jobs/sync/{ledger,engine,credentials,providers}
# ---------------------------------------------------------------------------------------------


@runtime_checkable
class Provider(Protocol):
    """A paginated incremental feed. Real adapters live in the generated product."""

    name: str
    version: str

    def fetch_page(self, cred: Credential, dataset: str, window: Window, cursor: str | None) -> Page: ...

    def parse_page(self, dataset: str, raw: bytes) -> Page:
        """Stored raw bytes back into a Page, with no network. Replay and crash recovery need it.
        Raises PermanentError if this connector version cannot read them."""
        ...


@runtime_checkable
class ReportProvider(Protocol):
    """An asynchronous report: request once, poll, download. Never re-request on a retry."""

    name: str
    version: str

    def request_report(self, cred: Credential, dataset: str, window: Window) -> str: ...
    def report_status(self, cred: Credential, report_id: str) -> ReportStatus: ...
    def download(self, cred: Credential, document_ref: str) -> Page: ...
    def parse_page(self, dataset: str, raw: bytes) -> Page: ...


@runtime_checkable
class TokenRefresher(Protocol):
    """Optional provider capability: exchange a credential for a fresh access token. Only ever called
    through `CredentialStore.refresh`, which serializes it per connection."""

    def refresh_token(self, cred: Credential) -> tuple[str, datetime | None]: ...


class RateBudgets(Protocol):
    """Provider quota blocks (session S2's budgets, as the runner uses them)."""

    def blocked_until(self, budget_key: str) -> datetime | None: ...
    def block(self, budget_key: str, until: datetime) -> None:
        """Block until `until`. A later block never shortens an existing one."""
        ...


class AuditSink(Protocol):
    """Writes an audit_events row with actor_type='system', in its own transaction."""

    def record(self, workspace_id: uuid.UUID, action: str, target_type: str, target_id: str,
               detail: Mapping[str, Any]) -> None: ...


class Ledger(Protocol):
    """Durable run state in Postgres (session S1). Every mutating call after claim carries the lease.

    Semantics the contract suite holds every implementation to:
    - `claim` counts as an attempt, and moves a queued or waiting run to running.
    - publishing an equal version replaces the record (a replay re-derives data); an older one is skipped.
    - `checkpoint` replaces the whole checkpoint.
    - `complete` raises if any raw object of the run is unprocessed.
    - `wait` sets status waiting and next_attempt_at, and leaves queue_job_id alone (the dispatcher
      re-queues waiting runs once they are due and their previous job has finished).
    """

    def create_run(self, spec: RunSpec) -> tuple[uuid.UUID, bool]:
        """(run_id, created). Same dedupe key → the existing run id and created=False."""
        ...

    def create_replay(self, source_run_id: uuid.UUID, connector_version: str,
                      requested_by: str | None = None) -> uuid.UUID:
        """A new queued outbox run of kind replay: the source run's window, `replay_of` set, and a
        dedupe key of its own, so each replay request is a separate run."""
        ...

    def get_run(self, run_id: uuid.UUID) -> RunView | None: ...

    def raw_objects(self, run_id: uuid.UUID) -> Sequence[RawObjectView]:
        """Every raw object the run saved, ordered by page_seq."""
        ...

    def claim(self, run_id: uuid.UUID, owner: str, lease_s: float) -> Lease | None:
        """None if another live lease holds the stream. A claim after expiry bumps the fence."""
        ...

    def heartbeat(self, lease: Lease, lease_s: float) -> Lease: ...

    def checkpoint(self, lease: Lease, stage: Stage, data: Mapping[str, Any]) -> None:
        """Save fetch progress (cursor, report id, page seq). Raises StaleLease on an old fence."""
        ...

    def save_raw(self, lease: Lease, page_seq: int, storage_key: str, sha256: str, size: int) -> uuid.UUID:
        """Record a raw object as saved and not yet processed (the replay backlog)."""
        ...

    def publish(self, lease: Lease, raw_object_id: uuid.UUID, records: Sequence[Record]) -> PublishResult:
        """In one transaction: upsert records (newer version wins), mark the raw object processed.
        Raises StaleLease on an old fence."""
        ...

    def complete(self, lease: Lease, window: Window, snapshot_complete: bool) -> None:
        """Advance coverage to include the window, only if every raw object of the run is processed.
        Coverage is one contiguous range and never spans a window that hasn't succeeded. A window that
        touches it extends it, and so do the succeeded windows that the extended range now touches (they
        may have succeeded earlier, past a hole this window fills). Deletions are inferred only when
        snapshot_complete is True."""
        ...

    def wait(self, lease: Lease, until: datetime, reason: str) -> None: ...
    def fail(self, lease: Lease, error_code: str, detail: str, request_ref: str | None) -> None: ...


class StaleLease(Exception):
    """A newer owner holds the stream. The holder of the old lease must stop without writing."""


class Engine(Protocol):
    """The queue (session S2, Procrastinate). Carries run ids, never payloads or secrets."""

    def enqueue(self, run_id: uuid.UUID, *, run_at: datetime | None = None, queue: str = "sync") -> None: ...
    def run_worker(self, *, queues: Sequence[str], until_idle: bool = False) -> None: ...


class CredentialStore(Protocol):
    """Encrypted credentials (session S3). Refresh is serialized per connection."""

    def get(self, connection_id: uuid.UUID) -> Credential: ...

    def rotate(self, cred: Credential, access_token: str, expires_at: datetime | None,
               extra: Mapping[str, str] | None = None) -> Credential:
        """Save a refreshed token only if `cred.version` is still current; else return the newer one."""
        ...

    def refresh(self, cred: Credential, refresher: TokenRefresher) -> Credential:
        """Refresh under the per-connection lock: if `cred.version` is still current, call the provider
        once and save the result; if another worker already refreshed, return its credential without
        calling the provider. AuthRevoked from the provider propagates."""
        ...

    def mark_revoked(self, connection_id: uuid.UUID, reason: str) -> None: ...
