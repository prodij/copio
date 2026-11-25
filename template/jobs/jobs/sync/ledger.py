"""PgLedger: the connector layer's durable run state, on the migration 0004 tables.

Spec: docs/superpowers/specs/2026-11-25-connector-layer-design.md (in the template repo).

How it stays correct when workers crash, retry or race:

- One row per stream (`sync_streams`, keyed by connection and dataset) holds the lease and a `fence`
  that grows on every claim. Every write after `claim` locks that row first, compares fences, and
  raises `StaleLease` before writing anything if a newer claim exists.
- Locks are always taken stream first, then run, then raw object, so two workers never deadlock.
- Raw first: `save_raw` records a page as an unprocessed raw object (the backlog). `publish` upserts
  its records and marks it processed in one transaction. `complete` refuses while any raw object of the
  run is unprocessed, so coverage never runs ahead of what is published.
- Stage, verify, publish atomically, with receipts (the idea comes from the copio-operations prototype):
  each publish stores a receipt and its sha256 on the raw object, each completion stores one on the run.
  A retried publish of the same raw bytes is answered from its verified receipt instead of repeated, and
  `verify_run` re-checks every receipt against its digest and the raw objects it names.
- Versions compare as text in byte order (`collate "C"`, which matches Python's `str` order), never in
  the database's locale order.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, Engine, Row, text

from jobs.sync.contract import (
    Lease,
    PublishResult,
    Record,
    RunKind,
    RunSpec,
    RunStatus,
    Stage,
    StaleLease,
    Window,
)

TERMINAL = frozenset({RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED})
MAX_DETAIL = 500
MAX_KEY = 1024
MAX_VERSION = 255


class RunNotFound(LookupError):
    """No sync_runs row with that id."""


class BacklogPending(RuntimeError):
    """`complete` was refused: some raw objects of the run are saved but not yet published."""


class RawObjectMismatch(ValueError):
    """The raw object does not belong to the lease's run (or, for a replay, to the run it replays)."""


class ReceiptMismatch(RuntimeError):
    """A stored receipt no longer matches its digest or the rows it describes."""


# ---------------------------------------------------------------------------------------------
# Receipts and sanitizing
# ---------------------------------------------------------------------------------------------


def canonical(value: Any) -> bytes:
    """One byte encoding per value, so a digest names exactly one receipt."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


_UUID = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
_AUTH_SCHEME = re.compile(r"(?i)\b(bearer|basic|token)\s+[A-Za-z0-9._~+/=-]{6,}")
_SECRET_FIELD = re.compile(
    r"(?i)\b(access[_-]?token|refresh[_-]?token|id[_-]?token|token|api[_-]?key|apikey|secret|"
    r"client[_-]?secret|password|passwd|authorization|signature|sig|session)"
    r"(\"?\s*[=:]\s*\"?)[^\s&\"',;}]+")
_OPAQUE = re.compile(r"[A-Za-z0-9+/_=-]{32,}")
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_CODE = re.compile(r"[a-z0-9][a-z0-9_.:-]{0,63}")
_REF_CHARS = re.compile(r"[^A-Za-z0-9._:/@-]")


def _redact_opaque(match: re.Match[str]) -> str:
    return match.group(0) if _UUID.fullmatch(match.group(0)) else "[redacted]"


def sanitize_detail(detail: str | None) -> str | None:
    """Make a message safe for `error_detail` / `wait_reason`: no credentials, no payload dumps.

    Redacts auth headers, `key=value` secrets and long opaque strings (tokens, keys, base64 blobs;
    UUIDs are kept), drops control characters and caps the length.
    """
    if detail is None:
        return None
    out = _CONTROL.sub(" ", detail)
    out = _AUTH_SCHEME.sub(lambda m: f"{m.group(1)} [redacted]", out)
    out = _SECRET_FIELD.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", out)
    out = _OPAQUE.sub(_redact_opaque, out)
    out = " ".join(out.split())
    return out if len(out) <= MAX_DETAIL else out[: MAX_DETAIL - 1] + "…"


def sanitize_code(code: str) -> str:
    code = code.strip().lower()
    return code if _CODE.fullmatch(code) else "unclassified"


def sanitize_ref(ref: str | None) -> str | None:
    if ref is None:
        return None
    ref = _REF_CHARS.sub("", ref)[:255]
    return ref or None


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(UTC)


def _check_window(window: Window) -> None:
    _aware(window.start, "window.start")
    _aware(window.end, "window.end")
    if window.start >= window.end:
        raise ValueError("window must be non-empty: start < end")


def _encode_record(record: Record) -> str | None:
    """The record's data as JSON, or None if the record cannot be stored as sent."""
    if not isinstance(record.key, str) or not 0 < len(record.key) <= MAX_KEY:
        return None
    if not isinstance(record.version, str) or not 0 < len(record.version) <= MAX_VERSION:
        return None
    if "\x00" in record.key or "\x00" in record.version or not isinstance(record.data, Mapping):
        return None
    try:
        data = canonical(dict(record.data)).decode()
    except (TypeError, ValueError):
        return None
    return None if "\\u0000" in data else data  # Postgres jsonb cannot hold NUL


# ---------------------------------------------------------------------------------------------
# The ledger
# ---------------------------------------------------------------------------------------------


class PgLedger:
    """`Ledger` on Postgres. Every method is one transaction.

    `clock` is injectable so tests can expire leases without sleeping; it must return aware datetimes.
    """

    def __init__(self, engine: Engine, *, clock: Callable[[], datetime] | None = None) -> None:
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))

    def _now(self) -> datetime:
        return _aware(self._clock(), "clock()")

    # -- runs -----------------------------------------------------------------------------------

    def create_run(self, spec: RunSpec) -> tuple[uuid.UUID, bool]:
        """Idempotent by `spec.dedupe_key()`. Raises LookupError if the connection is not in the
        spec's workspace."""
        _check_window(spec.window)
        key = spec.dedupe_key()
        with self._engine.begin() as conn:
            row = conn.execute(text(
                "insert into sync_runs (id, workspace_id, connection_id, dataset, kind, trigger,"
                " window_start, window_end, connector_version, dedupe_key, status, stage)"
                " select :id, c.workspace_id, c.id, :dataset, :kind, :trigger, :start, :end, :version,"
                " :key, :status, :stage from connections c"
                " where c.id = :connection_id and c.workspace_id = :workspace_id"
                " on conflict (dedupe_key) do nothing returning id"),
                {"id": uuid.uuid4(), "dataset": spec.dataset, "kind": str(spec.kind),
                 "trigger": str(spec.trigger), "start": spec.window.start, "end": spec.window.end,
                 "version": spec.connector_version, "key": key, "status": str(RunStatus.QUEUED),
                 "stage": str(Stage.PENDING), "connection_id": spec.connection_id,
                 "workspace_id": spec.workspace_id}).one_or_none()
            if row is not None:
                return row.id, True
            existing = conn.execute(text(
                "select id from sync_runs where dedupe_key = :key and workspace_id = :workspace_id"),
                {"key": key, "workspace_id": spec.workspace_id}).one_or_none()
        if existing is None:
            raise LookupError("connection not found in this workspace")
        return existing.id, False

    def claim(self, run_id: uuid.UUID, owner: str, lease_s: float) -> Lease | None:
        """Take the run's stream. None if another live lease holds it, or the run is finished, or the
        run has used all its attempts (it is then failed with `attempts_exhausted`)."""
        if lease_s <= 0:
            raise ValueError("lease_s must be positive")
        if not 0 < len(owner) <= 128:
            raise ValueError("owner must be 1-128 characters")
        now = self._now()
        with self._engine.begin() as conn:
            # Stream identity never changes, so read it unlocked, then lock stream before run.
            ident = conn.execute(text(
                "select workspace_id, connection_id, dataset from sync_runs where id = :id"),
                {"id": run_id}).one_or_none()
            if ident is None:
                raise RunNotFound(str(run_id))
            conn.execute(text(
                "insert into sync_streams (connection_id, dataset, workspace_id)"
                " values (:connection_id, :dataset, :workspace_id) on conflict do nothing"),
                ident._asdict())
            stream = conn.execute(text(
                "select fence, lease_run_id, lease_expires_at from sync_streams"
                " where connection_id = :connection_id and dataset = :dataset for update"),
                ident._asdict()).one()
            run = conn.execute(text(
                "select status, attempt, max_attempts from sync_runs where id = :id for update"),
                {"id": run_id}).one()
            if run.status in TERMINAL:
                return None
            if (stream.lease_run_id is not None and stream.lease_expires_at is not None
                    and stream.lease_expires_at > now):
                return None
            if run.attempt >= run.max_attempts:
                conn.execute(text(
                    "update sync_runs set status = :failed, error_code = 'attempts_exhausted',"
                    " error_detail = :detail, next_attempt_at = null, finished_at = :now"
                    " where id = :id"),
                    {"failed": str(RunStatus.FAILED), "now": now, "id": run_id,
                     "detail": f"stopped after {run.attempt} of {run.max_attempts} attempts"})
                return None
            expires = now + timedelta(seconds=lease_s)
            fence = conn.execute(text(
                "update sync_streams set fence = fence + 1, lease_run_id = :run_id, lease_owner = :owner,"
                " lease_expires_at = :expires, last_attempt_at = :now"
                " where connection_id = :connection_id and dataset = :dataset returning fence"),
                {"run_id": run_id, "owner": owner, "expires": expires, "now": now,
                 "connection_id": ident.connection_id, "dataset": ident.dataset}).scalar_one()
            conn.execute(text(
                "update sync_runs set status = :running, attempt = attempt + 1,"
                " started_at = coalesce(started_at, :now), next_attempt_at = null, wait_reason = null"
                " where id = :id"),
                {"running": str(RunStatus.RUNNING), "now": now, "id": run_id})
        return Lease(run_id=run_id, connection_id=ident.connection_id, dataset=ident.dataset,
                     owner=owner, fence=fence, expires_at=expires)

    def _fenced(self, conn: Connection, lease: Lease) -> Row[Any]:
        """Lock the stream, check the lease is current, lock and return the run. Raises StaleLease
        before anything is written."""
        stream = conn.execute(text(
            "select fence, lease_run_id from sync_streams"
            " where connection_id = :connection_id and dataset = :dataset for update"),
            {"connection_id": lease.connection_id, "dataset": lease.dataset}).one_or_none()
        if stream is None or stream.fence != lease.fence or stream.lease_run_id != lease.run_id:
            raise StaleLease(f"lease fence {lease.fence} on {lease.dataset} is no longer current")
        run = conn.execute(text(
            "select id, workspace_id, kind, status, attempt, max_attempts, replay_of, records_rejected"
            " from sync_runs where id = :id for update"), {"id": lease.run_id}).one()
        if run.status != RunStatus.RUNNING:
            raise StaleLease(f"run is {run.status}, not running")
        return run

    def _release(self, conn: Connection, lease: Lease) -> None:
        conn.execute(text(
            "update sync_streams set lease_run_id = null, lease_owner = null, lease_expires_at = null"
            " where connection_id = :connection_id and dataset = :dataset"),
            {"connection_id": lease.connection_id, "dataset": lease.dataset})

    def heartbeat(self, lease: Lease, lease_s: float) -> Lease:
        if lease_s <= 0:
            raise ValueError("lease_s must be positive")
        expires = self._now() + timedelta(seconds=lease_s)
        with self._engine.begin() as conn:
            self._fenced(conn, lease)
            conn.execute(text(
                "update sync_streams set lease_expires_at = :expires"
                " where connection_id = :connection_id and dataset = :dataset"),
                {"expires": expires, "connection_id": lease.connection_id, "dataset": lease.dataset})
        return replace(lease, expires_at=expires)

    def checkpoint(self, lease: Lease, stage: Stage, data: Mapping[str, Any]) -> None:
        """Set the stage and merge `data` into the run's checkpoint (keys not named are kept, so a
        report id saved earlier survives later cursor checkpoints)."""
        stage = Stage(stage)
        payload = canonical(dict(data)).decode()
        with self._engine.begin() as conn:
            self._fenced(conn, lease)
            conn.execute(text(
                "update sync_runs set stage = :stage, checkpoint = checkpoint || cast(:data as jsonb)"
                " where id = :id"), {"stage": str(stage), "data": payload, "id": lease.run_id})

    # -- raw and publish ------------------------------------------------------------------------

    def save_raw(self, lease: Lease, page_seq: int, storage_key: str, sha256: str, size: int) -> uuid.UUID:
        """Record a stored page as unprocessed. Saving the same page again with the same bytes returns
        the same id; with different bytes it replaces the entry and puts it back in the backlog."""
        if page_seq < 0 or size < 0:
            raise ValueError("page_seq and size must be non-negative")
        if not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        if not storage_key:
            raise ValueError("storage_key is required")
        now = self._now()
        with self._engine.begin() as conn:
            run = self._fenced(conn, lease)
            existing = conn.execute(text(
                "select id, storage_key, sha256, size_bytes from raw_objects"
                " where run_id = :run_id and page_seq = :seq for update"),
                {"run_id": lease.run_id, "seq": page_seq}).one_or_none()
            if existing is not None:
                if (existing.storage_key, existing.sha256, existing.size_bytes) != (storage_key, sha256, size):
                    conn.execute(text(
                        "update raw_objects set storage_key = :key, sha256 = :sha, size_bytes = :size,"
                        " fetched_at = :now, processed_at = null, receipt = null, receipt_sha256 = null"
                        " where id = :id"),
                        {"key": storage_key, "sha": sha256, "size": size, "now": now, "id": existing.id})
                raw_id: uuid.UUID = existing.id
                return raw_id
            raw_id = uuid.uuid4()
            conn.execute(text(
                "insert into raw_objects (id, run_id, workspace_id, connection_id, dataset, page_seq,"
                " storage_key, sha256, size_bytes, fetched_at)"
                " values (:id, :run_id, :workspace_id, :connection_id, :dataset, :seq, :key, :sha,"
                " :size, :now)"),
                {"id": raw_id, "run_id": lease.run_id, "workspace_id": run.workspace_id,
                 "connection_id": lease.connection_id, "dataset": lease.dataset, "seq": page_seq,
                 "key": storage_key, "sha": sha256, "size": size, "now": now})
        return raw_id

    def publish(self, lease: Lease, raw_object_id: uuid.UUID, records: Sequence[Record]) -> PublishResult:
        """In one transaction: verify the raw object, upsert records (a newer version wins; equal or
        older is skipped, except a replay may rewrite an equal version), mark the raw object processed
        with a receipt, and add the counts to the run."""
        now = self._now()
        with self._engine.begin() as conn:
            run = self._fenced(conn, lease)
            replay = run.kind == RunKind.REPLAY
            raw = conn.execute(text(
                "select id, run_id, connection_id, dataset, sha256, processed_at, receipt, receipt_sha256"
                " from raw_objects where id = :id for update"), {"id": raw_object_id}).one_or_none()
            if (raw is None or raw.connection_id != lease.connection_id or raw.dataset != lease.dataset
                    or not (raw.run_id == lease.run_id or (replay and raw.run_id == run.replay_of))):
                raise RawObjectMismatch("raw object is not part of this run")

            best: dict[str, tuple[Record, str]] = {}
            rejected = stale = 0
            for record in records:
                data = _encode_record(record)
                if data is None:
                    rejected += 1
                    continue
                prev = best.get(record.key)
                if prev is None:
                    best[record.key] = (record, data)
                else:
                    stale += 1
                    if record.version > prev[0].version:
                        best[record.key] = (record, data)
            records_sha = digest(canonical(sorted(
                [r.key, r.version, r.deleted, json.loads(d)] for r, d in best.values())))

            # A retry of a publish that already committed: answer from the verified receipt.
            if raw.processed_at is not None and raw.receipt is not None and not replay:
                receipt = self._verified(raw.receipt, raw.receipt_sha256, "raw object")
                if receipt.get("records_sha256") == records_sha and receipt.get("raw_sha256") == raw.sha256:
                    return PublishResult(receipt["accepted"], receipt["rejected"], receipt["stale_skipped"])

            accepted = 0
            for key in sorted(best):
                record, data = best[key]
                params = {"connection_id": lease.connection_id, "dataset": lease.dataset, "key": key,
                          "workspace_id": run.workspace_id, "version": record.version, "data": data,
                          "deleted": record.deleted, "run_id": lease.run_id, "raw_id": raw_object_id,
                          "now": now, "replay": replay}
                won = conn.execute(text(
                    "insert into synced_records (connection_id, dataset, record_key, workspace_id, version,"
                    " data, deleted, run_id, raw_object_id, published_at, last_seen_run_id)"
                    " values (:connection_id, :dataset, :key, :workspace_id, :version,"
                    " cast(:data as jsonb), :deleted, :run_id, :raw_id, :now, :run_id)"
                    " on conflict (connection_id, dataset, record_key) do update set"
                    " version = excluded.version, data = excluded.data, deleted = excluded.deleted,"
                    " run_id = excluded.run_id, raw_object_id = excluded.raw_object_id,"
                    " published_at = excluded.published_at, last_seen_run_id = excluded.last_seen_run_id"
                    ' where synced_records.version collate "C" < excluded.version collate "C"'
                    ' or (:replay and synced_records.version collate "C" = excluded.version collate "C")'
                    " returning record_key"), params).one_or_none()
                if won is not None:
                    accepted += 1
                else:
                    stale += 1
                    conn.execute(text(
                        "update synced_records set last_seen_run_id = :run_id where connection_id ="
                        " :connection_id and dataset = :dataset and record_key = :key"), params)

            receipt = {"kind": "raw_publish", "raw_object_id": str(raw_object_id),
                       "raw_sha256": raw.sha256, "run_id": str(lease.run_id), "fence": lease.fence,
                       "records_sha256": records_sha, "accepted": accepted, "rejected": rejected,
                       "stale_skipped": stale, "published_at": now.isoformat()}
            encoded = canonical(receipt)
            conn.execute(text(
                "update raw_objects set processed_at = :now, receipt = cast(:receipt as jsonb),"
                " receipt_sha256 = :sha where id = :id"),
                {"now": now, "receipt": encoded.decode(), "sha": digest(encoded), "id": raw_object_id})
            conn.execute(text(
                "update sync_runs set records_accepted = records_accepted + :a,"
                " records_rejected = records_rejected + :r, records_stale = records_stale + :s"
                " where id = :id"), {"a": accepted, "r": rejected, "s": stale, "id": lease.run_id})
        return PublishResult(accepted=accepted, rejected=rejected, stale_skipped=stale)

    # -- finishing ------------------------------------------------------------------------------

    def complete(self, lease: Lease, window: Window, snapshot_complete: bool) -> None:
        """Finish the run as succeeded. Raises BacklogPending (writing nothing) while any raw object of
        the run is unprocessed. Coverage grows only contiguously: a window that overlaps or touches the
        covered range extends it; a window past a gap leaves coverage as it is. Deletions are inferred
        only for a complete snapshot with no rejected records: keys the run did not see are tombstoned."""
        _check_window(window)
        now = self._now()
        with self._engine.begin() as conn:
            run = self._fenced(conn, lease)
            run_ids = [lease.run_id] + ([run.replay_of] if run.kind == RunKind.REPLAY and run.replay_of else [])
            raws = conn.execute(text(
                "select id, page_seq, sha256, processed_at, receipt_sha256 from raw_objects"
                " where run_id = any(:ids) order by run_id = :run_id desc, page_seq"),
                {"ids": run_ids, "run_id": lease.run_id}).all()
            pending = sum(1 for r in raws if r.processed_at is None)
            if pending:
                raise BacklogPending(f"{pending} raw object(s) of this run are not published yet")

            deleted = 0
            skipped: str | None = None
            if snapshot_complete:
                if not raws:
                    skipped = "no_raw_objects"
                elif run.records_rejected:
                    skipped = "rejected_records"
                else:
                    deleted = conn.execute(text(
                        "update synced_records set deleted = true, run_id = :run_id, published_at = :now"
                        " where connection_id = :connection_id and dataset = :dataset and not deleted"
                        " and last_seen_run_id is distinct from :run_id"),
                        {"run_id": lease.run_id, "now": now, "connection_id": lease.connection_id,
                         "dataset": lease.dataset}).rowcount

            stream = conn.execute(text(
                "select covered_from, covered_to from sync_streams"
                " where connection_id = :connection_id and dataset = :dataset"),
                {"connection_id": lease.connection_id, "dataset": lease.dataset}).one()
            start, end = stream.covered_from, stream.covered_to
            contiguous = True
            if start is None or end is None:
                start, end = window.start, window.end
            elif window.start <= end and window.end >= start:
                start, end = min(start, window.start), max(end, window.end)
            else:
                contiguous = False
            advanced = (start, end) != (stream.covered_from, stream.covered_to)
            conn.execute(text(
                "update sync_streams set covered_from = :start, covered_to = :end, last_publish_at = :now,"
                " last_publish_run_id = :run_id, lease_run_id = null, lease_owner = null,"
                " lease_expires_at = null where connection_id = :connection_id and dataset = :dataset"),
                {"start": start, "end": end, "now": now, "run_id": lease.run_id,
                 "connection_id": lease.connection_id, "dataset": lease.dataset})

            counts = conn.execute(text(
                "select records_accepted, records_rejected, records_stale from sync_runs where id = :id"),
                {"id": lease.run_id}).one()
            receipt = {"kind": "run_complete", "run_id": str(lease.run_id), "fence": lease.fence,
                       "attempt": run.attempt, "window": [window.start.isoformat(), window.end.isoformat()],
                       "snapshot_complete": snapshot_complete, "deletions_inferred": deleted,
                       "deletion_skipped": skipped, "contiguous": contiguous,
                       "coverage_advanced": advanced,
                       "coverage": [_aware(start, "covered_from").isoformat(),
                                    _aware(end, "covered_to").isoformat()],
                       "raw_objects": [[str(r.id), r.sha256, r.receipt_sha256] for r in raws],
                       "records_accepted": counts.records_accepted,
                       "records_rejected": counts.records_rejected,
                       "records_stale": counts.records_stale, "completed_at": now.isoformat()}
            encoded = canonical(receipt)
            conn.execute(text(
                "update sync_runs set status = :succeeded, stage = :published, finished_at = :now,"
                " next_attempt_at = null, wait_reason = null, error_code = null, error_detail = null,"
                " receipt = cast(:receipt as jsonb), receipt_sha256 = :sha where id = :id"),
                {"succeeded": str(RunStatus.SUCCEEDED), "published": str(Stage.PUBLISHED), "now": now,
                 "receipt": encoded.decode(), "sha": digest(encoded), "id": lease.run_id})

    def wait(self, lease: Lease, until: datetime, reason: str, *, request_ref: str | None = None) -> None:
        """Yield the stream until `until` (rate limit, report still processing). Keeps stage and
        checkpoint; releases the lease. `request_ref` is an S1 addition to the contract signature."""
        until = _aware(until, "until")
        with self._engine.begin() as conn:
            self._fenced(conn, lease)
            conn.execute(text(
                "update sync_runs set status = :waiting, next_attempt_at = :until, wait_reason = :reason,"
                " provider_request_ref = coalesce(:ref, provider_request_ref) where id = :id"),
                {"waiting": str(RunStatus.WAITING), "until": until, "reason": sanitize_detail(reason),
                 "ref": sanitize_ref(request_ref), "id": lease.run_id})
            self._release(conn, lease)

    def fail(self, lease: Lease, error_code: str, detail: str, request_ref: str | None,
             *, retry_at: datetime | None = None) -> None:
        """Record a failed attempt and release the lease. With `retry_at` (an S1 addition) and attempts
        left, the run waits until then; otherwise it is failed for good."""
        retry_at = _aware(retry_at, "retry_at") if retry_at is not None else None
        now = self._now()
        code = sanitize_code(error_code)
        with self._engine.begin() as conn:
            run = self._fenced(conn, lease)
            retry = retry_at is not None and run.attempt < run.max_attempts
            conn.execute(text(
                "update sync_runs set status = :status, next_attempt_at = :next, wait_reason = :reason,"
                " error_code = :code, error_detail = :detail,"
                " provider_request_ref = coalesce(:ref, provider_request_ref),"
                " finished_at = :finished where id = :id"),
                {"status": str(RunStatus.WAITING if retry else RunStatus.FAILED),
                 "next": retry_at if retry else None,
                 "reason": f"retry after {code}" if retry else None, "code": code,
                 "detail": sanitize_detail(detail), "ref": sanitize_ref(request_ref),
                 "finished": None if retry else now, "id": lease.run_id})
            self._release(conn, lease)

    # -- receipts -------------------------------------------------------------------------------

    @staticmethod
    def _verified(receipt: Any, sha: str | None, what: str) -> dict[str, Any]:
        if not isinstance(receipt, dict) or sha is None or digest(canonical(receipt)) != sha:
            raise ReceiptMismatch(f"{what} receipt does not match its digest")
        return receipt

    def run_receipt(self, run_id: uuid.UUID) -> dict[str, Any] | None:
        """The completion receipt, verified against its digest. None until the run completes."""
        with self._engine.connect() as conn:
            row = conn.execute(text("select receipt, receipt_sha256 from sync_runs where id = :id"),
                               {"id": run_id}).one_or_none()
        if row is None:
            raise RunNotFound(str(run_id))
        return None if row.receipt is None else self._verified(row.receipt, row.receipt_sha256, "run")

    def verify_run(self, run_id: uuid.UUID) -> dict[str, Any]:
        """Re-check a completed run: its receipt, every raw object's receipt, and that the raw objects
        the run receipt names are exactly the ones stored, unchanged. Raises ReceiptMismatch."""
        receipt = self.run_receipt(run_id)
        if receipt is None:
            raise ReceiptMismatch("run has no completion receipt")
        ids = [uuid.UUID(raw_id) for raw_id, _, _ in receipt["raw_objects"]]
        with self._engine.connect() as conn:
            rows = {r.id: r for r in conn.execute(text(
                "select id, sha256, processed_at, receipt, receipt_sha256 from raw_objects"
                " where id = any(:ids)"), {"ids": ids})}
        for raw_id, sha, receipt_sha in receipt["raw_objects"]:
            row = rows.get(uuid.UUID(raw_id))
            if row is None or row.sha256 != sha or row.processed_at is None or row.receipt_sha256 != receipt_sha:
                raise ReceiptMismatch("a raw object changed after the run completed")
            self._verified(row.receipt, row.receipt_sha256, "raw object")
        return receipt
