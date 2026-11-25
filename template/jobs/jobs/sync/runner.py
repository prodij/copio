"""The sync runner: executes one run, given only its id.

    claim → fetch (incremental pages | report lifecycle | replay of stored raw)
          → store raw (RawStore) → save_raw → publish → checkpoint → … → complete

Every write after `claim` carries the lease; a newer owner turns it into `StaleLease`, and the runner
stops without writing anything else. The runner never sleeps: anything that has to wait (a rate limit,
a retry, a report still processing, a paused connection) checkpoints, calls `ledger.wait`, and returns,
so the worker is free and the run is picked up again at `next_attempt_at`.

Nothing a provider sends (message, payload, token) is ever copied into a log line or `error_detail`.
Errors are recorded as a fixed code, a fixed sentence, the exception class and the provider's request
reference.

Spec: docs/superpowers/specs/2026-11-25-connector-layer-design.md (in the template repo).
"""

from __future__ import annotations

import enum
import hashlib
import logging
import random
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, NoReturn, Protocol, runtime_checkable

from jobs.storage import RawStore
from jobs.sync.contract import (
    AuthRevoked,
    ConnectionState,
    Credential,
    CredentialStore,
    Lease,
    Ledger,
    Page,
    PermanentError,
    Provider,
    ProviderError,
    RateLimited,
    ReportProvider,
    ReportState,
    RunKind,
    RunSpec,
    RunStatus,
    Stage,
    StaleLease,
    TransientError,
)

log = logging.getLogger("jobs.sync.runner")

TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})


# ---------------------------------------------------------------------------------------------
# What the runner needs beyond contract.py. Each is a proposed contract addition (see the S4 report);
# until the integrator adopts them they live here so the runner can be built and tested.
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunView:
    """A read of one sync_runs row. Proposed: `Ledger.get_run`."""

    run_id: uuid.UUID
    spec: RunSpec
    status: RunStatus
    stage: Stage
    checkpoint: Mapping[str, Any]
    attempt: int  # number of claims so far (claim increments it)
    max_attempts: int
    replay_of: uuid.UUID | None = None


@dataclass(frozen=True)
class RawObjectView:
    """A read of one raw_objects row. Proposed: `Ledger.raw_objects`."""

    id: uuid.UUID
    run_id: uuid.UUID
    page_seq: int
    storage_key: str
    sha256: str
    size: int
    processed: bool


class RunLedger(Ledger, Protocol):
    def get_run(self, run_id: uuid.UUID) -> RunView | None: ...
    def raw_objects(self, run_id: uuid.UUID) -> Sequence[RawObjectView]:
        """All raw objects saved by the run, any order."""
        ...


@runtime_checkable
class PageParser(Protocol):
    """Turns stored raw bytes back into a Page. Needed for replay and for crash recovery (a raw object
    saved but not published). Proposed: part of Provider and ReportProvider."""

    def parse_page(self, dataset: str, raw: bytes) -> Page: ...


@runtime_checkable
class TokenRefresher(Protocol):
    """Exchanges a credential for a fresh access token. Proposed: optional Provider capability."""

    def refresh_token(self, cred: Credential) -> tuple[str, datetime | None]: ...


class Clock(Protocol):
    def now(self) -> datetime: ...


class RateBudgets(Protocol):
    """The slice of S2's budgets the runner uses: honor and set `rate_budgets.blocked_until`."""

    def blocked_until(self, budget_key: str) -> datetime | None: ...
    def block(self, budget_key: str, until: datetime) -> None: ...


class AuditSink(Protocol):
    """Writes an `audit_events` row with actor_type='system'."""

    def record(self, workspace_id: uuid.UUID, action: str, target_type: str, target_id: str,
               detail: Mapping[str, Any]) -> None: ...


class SystemClock:
    def now(self) -> datetime:
        return datetime.now(UTC)


# ---------------------------------------------------------------------------------------------
# Configuration and dependencies
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class RunnerPolicy:
    lease_s: float = 60.0
    heartbeat_fraction: float = 0.5
    backfill_pages_per_claim: int = 5
    report_poll_interval_s: float = 30.0
    max_report_polls: int = 20
    max_rate_limit_waits: int = 10
    rate_limit_default_s: float = 30.0
    rate_limit_jitter_fraction: float = 0.2
    retry_base_s: float = 2.0
    retry_cap_s: float = 300.0
    min_retry_delay_s: float = 1.0
    max_claims_per_run: int = 25
    pause_recheck_s: float = 300.0
    refresh_skew_s: float = 60.0
    # Datasets whose provider returns the full current set; a fetch that ends without
    # complete_snapshot is partial and does not complete the run.
    snapshot_datasets: frozenset[str] = frozenset()


AnyProvider = Provider | ReportProvider


@dataclass
class RunnerDeps:
    ledger: RunLedger
    credentials: CredentialStore
    raw_store: RawStore
    providers: Callable[[RunSpec], AnyProvider]
    budgets: RateBudgets
    audit: AuditSink
    connection_state: Callable[[uuid.UUID], ConnectionState]
    clock: Clock = field(default_factory=SystemClock)
    owner: str = "worker"
    policy: RunnerPolicy = field(default_factory=RunnerPolicy)
    rng: random.Random = field(default_factory=random.Random)


class Outcome(enum.StrEnum):
    SUCCEEDED = "succeeded"
    WAITING = "waiting"  # yielded; the run has next_attempt_at
    FAILED = "failed"
    STALE = "stale"  # lost the lease to a newer owner; stopped without writing
    BUSY = "busy"  # another live lease holds the stream; nothing was written
    NOOP = "noop"  # the run is already terminal (a duplicate delivery)


class _Stop(Exception):  # internal control flow; never escapes execute()
    def __init__(self, outcome: Outcome) -> None:
        super().__init__(outcome.value)
        self.outcome = outcome


_REF_SAFE = re.compile(r"[^A-Za-z0-9._:/-]")


def _safe_ref(ref: str | None) -> str | None:
    """A provider request reference, restricted to an id-like shape so it can never carry a payload."""
    if not ref:
        return None
    return _REF_SAFE.sub("", ref)[:255] or None


# ---------------------------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------------------------


def execute(run_id: uuid.UUID, deps: RunnerDeps) -> Outcome:
    """Run one unit of work for `run_id`. Safe to call twice, concurrently, or after a crash."""
    run = deps.ledger.get_run(run_id)
    if run is None or run.status in TERMINAL:
        log.info("sync run %s: nothing to do", run_id)
        return Outcome.NOOP
    lease = deps.ledger.claim(run_id, deps.owner, deps.policy.lease_s)
    if lease is None:
        log.info("sync run %s: stream is leased by another worker", run_id)
        return Outcome.BUSY
    try:
        outcome = _Execution(run_id, lease, deps).go()
    except StaleLease:
        log.info("sync run %s: lease taken over by a newer owner; stopping", run_id)
        outcome = Outcome.STALE
    log.info("sync run %s: %s", run_id, outcome.value)
    return outcome


class _Execution:
    def __init__(self, run_id: uuid.UUID, lease: Lease, deps: RunnerDeps) -> None:
        self.deps = deps
        self.ledger = deps.ledger
        self.policy = deps.policy
        self.lease = lease
        run = deps.ledger.get_run(run_id)
        if run is None:  # claimed a run that no longer exists: treat as lost
            raise StaleLease(str(run_id))
        self.run = run
        self.spec = run.spec
        self.cp: dict[str, Any] = dict(run.checkpoint)
        self.stage = run.stage
        self.may_store_carried_raw = True

    # --- top level ---------------------------------------------------------------------------

    def go(self) -> Outcome:
        try:
            self._go()
        except _Stop as stop:
            return stop.outcome

    def _go(self) -> NoReturn:
        if self.run.attempt > self.policy.max_claims_per_run:
            self.fail("attempts_exhausted", "the run was claimed too many times without finishing")
        state = self.deps.connection_state(self.spec.connection_id)
        if state in (ConnectionState.RECONNECT_NEEDED, ConnectionState.DISCONNECTED):
            self.fail("connection_unavailable", f"the connection is {state.value}")
        if state is ConnectionState.PAUSED:
            self.wait(self.policy.pause_recheck_s, "connection_paused")
        provider = self.deps.providers(self.spec)
        self.cp.setdefault("connector_version", provider.version)
        try:
            if self.spec.kind is RunKind.REPLAY:
                self.replay(provider)
            self.honor_budget()
            cred = self.credential(provider)
            if self.spec.kind is RunKind.REPORT:
                if not isinstance(provider, ReportProvider):
                    self.fail("provider_mismatch", "a report run needs a report provider")
                self.report(provider, cred)
            if not isinstance(provider, Provider):
                self.fail("provider_mismatch", "a page run needs a paginated provider")
            self.pages(provider, cred)
        except RateLimited as exc:
            self.on_rate_limited(exc)
        except TransientError as exc:
            self.on_transient(exc)
        except AuthRevoked as exc:
            self.deps.credentials.mark_revoked(self.spec.connection_id, "provider rejected the credential")
            self.fail("auth_revoked", "the provider rejected the credential; reconnect needed", exc)
        except PermanentError as exc:
            self.on_permanent(exc)

    # --- incremental / backfill pages ----------------------------------------------------------

    def pages(self, provider: Provider, cred: Credential) -> NoReturn:
        self.recover_backlog(provider)
        pages_this_claim = 0
        while not self.cp.get("fetch_complete"):
            if (self.spec.kind is RunKind.BACKFILL
                    and pages_this_claim >= self.policy.backfill_pages_per_claim):
                self.wait(0.0, "backfill_yield")  # let other work on this stream run
            if pages_this_claim and self.deps.connection_state(
                    self.spec.connection_id) is ConnectionState.PAUSED:
                self.wait(self.policy.pause_recheck_s, "connection_paused")
            self.keep_alive()
            page = provider.fetch_page(cred, self.spec.dataset, self.spec.window, self.cp.get("cursor"))
            self.store_and_publish(provider, page)
            pages_this_claim += 1
            self.after_page(page)
        self.finish()

    def after_page(self, page: Page) -> None:
        self.cp["page_seq"] = int(self.cp.get("page_seq", 0)) + 1
        self.cp["cursor"] = page.next_cursor
        self.cp["snapshot_complete"] = page.complete_snapshot
        if page.next_cursor is None:
            if (self.spec.dataset in self.policy.snapshot_datasets and not page.complete_snapshot):
                # A partial snapshot: keep what was published, never infer deletions, never advance
                # coverage. Start the snapshot over, as a bounded retry.
                self.cp["cursor"] = None
                self.retry_later("partial_snapshot", "the provider returned an incomplete snapshot")
            self.cp["fetch_complete"] = True
            self.save_checkpoint(Stage.FETCHED)
        else:
            self.save_checkpoint(Stage.FETCHING)

    # --- report lifecycle ----------------------------------------------------------------------

    def report(self, provider: ReportProvider, cred: Credential) -> NoReturn:
        self.recover_backlog(provider)
        if self.cp.get("fetch_complete"):
            self.finish()
        report_id = self.cp.get("report_id")
        if report_id is None:
            if self.cp.get("report_requesting"):
                # A worker died between asking for the report and saving its id. Asking again could
                # produce a second report; an operator retry decides instead.
                self.fail("report_request_lost", "the report was requested but its id was not saved")
            self.cp["report_requesting"] = True
            self.save_checkpoint(Stage.PENDING)
            self.keep_alive()
            report_id = provider.request_report(cred, self.spec.dataset, self.spec.window)
            self.cp.pop("report_requesting", None)
            self.cp["report_id"] = report_id
            self.cp["report_requests"] = int(self.cp.get("report_requests", 0)) + 1
            self.save_checkpoint(Stage.REQUESTED)
        polls = int(self.cp.get("polls", 0))
        if polls >= self.policy.max_report_polls:
            self.fail("report_poll_exhausted", "the report did not finish within the poll budget")
        self.keep_alive()
        status = provider.report_status(cred, str(report_id))
        self.cp["polls"] = polls + 1
        self.cp["report_state"] = status.state.value
        if status.state in (ReportState.QUEUED, ReportState.PROCESSING):
            self.save_checkpoint(Stage.REQUESTED)
            self.wait(self.policy.report_poll_interval_s, "report_processing")
        if status.state is ReportState.FATAL:
            self.fail("report_fatal", "the provider reported the report as failed", status.request_ref)
        if status.state is ReportState.CANCELLED_NO_DATA:
            self.cp["fetch_complete"] = True
            self.cp["snapshot_complete"] = False
            self.save_checkpoint(Stage.FETCHED)
            self.finish()
        if status.document_ref is None:
            self.fail("report_no_document", "the report is done but has no document", status.request_ref)
        self.keep_alive()
        page = provider.download(cred, status.document_ref)
        self.store_and_publish(provider, page)
        self.cp["page_seq"] = int(self.cp.get("page_seq", 0)) + 1
        self.cp["fetch_complete"] = True
        self.cp["snapshot_complete"] = page.complete_snapshot
        self.save_checkpoint(Stage.FETCHED)
        self.finish()

    # --- replay --------------------------------------------------------------------------------

    def replay(self, provider: AnyProvider) -> NoReturn:
        """Re-publish a finished run's stored raw objects with the current connector. Never calls the
        provider. Completes coverage only if the source run fetched its whole window."""
        self.may_store_carried_raw = False
        source = self.ledger.get_run(self.run.replay_of) if self.run.replay_of else None
        if source is None:
            self.fail("replay_source_missing", "the run to replay does not exist")
        if not isinstance(provider, PageParser):
            self.fail("replay_unsupported", "this connector cannot parse stored raw objects")
        raws = sorted(self.ledger.raw_objects(source.run_id), key=lambda r: r.page_seq)
        start = int(self.cp.get("replay_index", 0))
        for index in range(start, len(raws)):
            raw = raws[index]
            self.keep_alive()
            page = provider.parse_page(self.spec.dataset, self.load_raw(raw))
            self.ledger.publish(self.lease, raw.id, page.records)
            self.cp["replay_index"] = index + 1
            self.save_checkpoint(Stage.FETCHING)
        detail = {"replay_of": str(source.run_id), "connector_version": provider.version,
                  "source_connector_version": source.spec.connector_version,
                  "raw_objects": len(raws)}
        if not source.checkpoint.get("fetch_complete"):
            self.audit("run.replay", {**detail, "coverage_advanced": False})
            self.fail("replay_source_incomplete",
                      "records republished; the source run never fetched its whole window")
        self.cp["fetch_complete"] = True
        self.save_checkpoint(Stage.FETCHED)
        self.ledger.complete(self.lease, source.spec.window,
                             bool(source.checkpoint.get("snapshot_complete")))
        self.audit("run.replay", {**detail, "coverage_advanced": True})
        raise _Stop(Outcome.SUCCEEDED)

    # --- shared steps --------------------------------------------------------------------------

    def recover_backlog(self, provider: AnyProvider) -> None:
        """Catch up after a worker died mid-page. Raw objects this run saved but never published are
        published now, and raw objects the checkpoint has not moved past (death between publish and
        checkpoint) move it forward, so no page is fetched or recorded twice."""
        done = int(self.cp.get("page_seq", 0))
        behind = sorted((r for r in self.ledger.raw_objects(self.run.run_id)
                         if not r.processed or r.page_seq >= done), key=lambda r: r.page_seq)
        if not behind:
            return
        if not isinstance(provider, PageParser):
            self.fail("backlog_unparseable", "saved raw objects cannot be parsed by this connector")
        self.may_store_carried_raw = False  # the raw is already stored
        for raw in behind:
            self.keep_alive()
            page = provider.parse_page(self.spec.dataset, self.load_raw(raw))
            if not raw.processed:
                self.ledger.publish(self.lease, raw.id, page.records)
            if raw.page_seq < int(self.cp.get("page_seq", 0)):
                continue  # the checkpoint already moved past this page
            self.cp["page_seq"] = raw.page_seq
            if self.spec.kind is RunKind.REPORT:
                self.cp["page_seq"] = raw.page_seq + 1
                self.cp["fetch_complete"] = True
                self.cp["snapshot_complete"] = page.complete_snapshot
                self.save_checkpoint(Stage.FETCHED)
            else:
                self.after_page(page)
        self.may_store_carried_raw = True

    def load_raw(self, raw: RawObjectView) -> bytes:
        body = self.deps.raw_store.get(raw.storage_key)
        if hashlib.sha256(body).hexdigest() != raw.sha256 or len(body) != raw.size:
            self.fail("raw_corrupt", "a stored raw object does not match its recorded checksum")
        return body

    def store_raw(self, provider_name: str, body: bytes, ext: str) -> uuid.UUID:
        seq = int(self.cp.get("page_seq", 0))
        # The fence is in the key, so a stale worker can never overwrite the current owner's object.
        key = self.deps.raw_store.put_raw(
            f"{provider_name}/{self.spec.dataset}", str(self.spec.workspace_id),
            f"{self.run.run_id}/f{self.lease.fence}-p{seq:06d}", ext, body,
            self.deps.clock.now().date())
        self.keep_alive()
        return self.ledger.save_raw(self.lease, seq, key, hashlib.sha256(body).hexdigest(), len(body))

    def store_and_publish(self, provider: AnyProvider, page: Page) -> None:
        raw_id = self.store_raw(provider.name, page.raw, page.raw_ext)
        result = self.ledger.publish(self.lease, raw_id, page.records)
        self.cp["accepted"] = int(self.cp.get("accepted", 0)) + result.accepted
        self.cp["stale_skipped"] = int(self.cp.get("stale_skipped", 0)) + result.stale_skipped
        self.cp["rejected"] = int(self.cp.get("rejected", 0)) + result.rejected

    def finish(self) -> NoReturn:
        if any(not r.processed for r in self.ledger.raw_objects(self.run.run_id)):
            self.fail("backlog_unprocessed", "raw objects of this run are not published yet")
        self.ledger.complete(self.lease, self.spec.window, bool(self.cp.get("snapshot_complete")))
        raise _Stop(Outcome.SUCCEEDED)

    def credential(self, provider: AnyProvider) -> Credential:
        cred = self.deps.credentials.get(self.spec.connection_id)
        now = self.deps.clock.now()
        if (cred.expires_at is not None and isinstance(provider, TokenRefresher)
                and cred.expires_at - now <= timedelta(seconds=self.policy.refresh_skew_s)):
            self.keep_alive()
            token, expires_at = provider.refresh_token(cred)
            # rotate is version-checked: if another worker refreshed first, theirs wins and comes back.
            cred = self.deps.credentials.rotate(cred, token, expires_at)
        return cred

    def honor_budget(self) -> None:
        key = self.cp.get("budget_key")
        if not key:
            return
        until = self.deps.budgets.blocked_until(str(key))
        now = self.deps.clock.now()
        if until is not None and until > now:
            self.wait((until - now).total_seconds(), "rate_limited")

    def keep_alive(self) -> None:
        remaining = (self.lease.expires_at - self.deps.clock.now()).total_seconds()
        if remaining < self.policy.lease_s * self.policy.heartbeat_fraction:
            self.lease = self.ledger.heartbeat(self.lease, self.policy.lease_s)
            self.cp["heartbeats"] = int(self.cp.get("heartbeats", 0)) + 1

    def save_checkpoint(self, stage: Stage) -> None:
        self.stage = stage
        self.ledger.checkpoint(self.lease, stage, dict(self.cp))

    def audit(self, action: str, detail: Mapping[str, Any]) -> None:
        self.deps.audit.record(self.spec.workspace_id, action, "sync_run", str(self.run.run_id), detail)

    # --- error mapping -------------------------------------------------------------------------

    def on_rate_limited(self, exc: RateLimited) -> NoReturn:
        self.cp.pop("report_requesting", None)  # the provider answered; nothing was created
        waits = int(self.cp.get("rate_limit_waits", 0)) + 1
        self.cp["rate_limit_waits"] = waits
        if waits > self.policy.max_rate_limit_waits:
            self.fail("rate_limit_exhausted", "the provider kept rate limiting this run", exc)
        delay = max(exc.retry_after_s if exc.retry_after_s is not None else self.policy.rate_limit_default_s,
                    self.policy.min_retry_delay_s)
        delay += self.deps.rng.uniform(0, delay * self.policy.rate_limit_jitter_fraction)
        until = self.deps.clock.now() + timedelta(seconds=delay)
        self.deps.budgets.block(exc.budget_key, until)
        self.cp["budget_key"] = exc.budget_key
        self.wait(delay, "rate_limited")

    def on_transient(self, exc: TransientError) -> NoReturn:
        self.cp.pop("report_requesting", None)
        self.retry_later("transient_exhausted", "the provider kept failing transiently", exc)

    def on_permanent(self, exc: PermanentError) -> NoReturn:
        carried = getattr(exc, "raw", None)
        if self.may_store_carried_raw and isinstance(carried, bytes):
            # Keep the body that could not be parsed, so a fixed connector can replay it. It stays in
            # the backlog, so coverage cannot advance past it.
            self.store_raw("unparsed", carried, "json")
            self.cp["page_seq"] = int(self.cp.get("page_seq", 0)) + 1
            self.save_checkpoint(self.stage)
        self.fail("permanent", "the provider request cannot succeed as sent", exc)

    def retry_later(self, code: str, sentence: str, exc: ProviderError | None = None) -> NoReturn:
        failures = int(self.cp.get("failures", 0)) + 1
        self.cp["failures"] = failures
        if failures >= self.run.max_attempts:
            self.fail(code, sentence, exc)
        ceiling = min(self.policy.retry_cap_s, self.policy.retry_base_s * 2 ** (failures - 1))
        delay = max(self.policy.min_retry_delay_s, self.deps.rng.uniform(0, ceiling))  # full jitter
        self.wait(delay, "retry")

    # --- terminal moves (each raises _Stop) ----------------------------------------------------

    def wait(self, delay_s: float, reason: str) -> NoReturn:
        self.save_checkpoint(self.stage)
        until = self.deps.clock.now() + timedelta(seconds=max(0.0, delay_s))
        self.ledger.wait(self.lease, until, reason)
        log.info("sync run %s: waiting %.1fs (%s)", self.run.run_id, delay_s, reason)
        raise _Stop(Outcome.WAITING)

    def fail(self, code: str, sentence: str,
             exc: ProviderError | str | None = None) -> NoReturn:
        ref: str | None = None
        detail = sentence
        if isinstance(exc, ProviderError):
            ref = exc.request_ref
            detail = f"{sentence} ({type(exc).__name__})"
        elif isinstance(exc, str):
            ref = exc
        self.save_checkpoint(self.stage)
        self.ledger.fail(self.lease, code, detail, _safe_ref(ref))
        log.warning("sync run %s failed: %s", self.run.run_id, code)
        raise _Stop(Outcome.FAILED)
