"""ORM view of the connector layer's tables (migration 0004). The backend reads and manages these; the
jobs worker writes runs, streams, raw objects and records through jobs/jobs/sync/ledger.py.

Owned by the integrator. Sessions add their own models in their own modules, not here.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    provider: Mapped[str] = mapped_column(String(64))
    account_ref: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(24), default="healthy")
    state_reason: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list[str]] = mapped_column(JSONB, default=list)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Credential(Base):
    """Never serialize this model into a response."""

    __tablename__ = "credentials"

    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"),
                                                     primary_key=True)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    key_id: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SyncSchedule(Base):
    __tablename__ = "sync_schedules"

    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"),
                                                     primary_key=True)
    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), default="incremental")
    cron: Mapped[str] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    jitter_s: Mapped[int] = mapped_column(Integer, default=0)
    overlap: Mapped[str] = mapped_column(String(16), default="skip")
    catchup_window_s: Mapped[int] = mapped_column(Integer, default=3600)
    lookback_s: Mapped[int] = mapped_column(Integer, default=0)
    paused: Mapped[bool] = mapped_column(Boolean, default=False)
    next_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncRun(Base):
    __tablename__ = "sync_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    trigger: Mapped[str] = mapped_column(String(16))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    connector_version: Mapped[str] = mapped_column(String(64))
    dedupe_key: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    stage: Mapped[str] = mapped_column(String(16), default="pending")
    attempt: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wait_reason: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail: Mapped[str | None] = mapped_column(Text)
    provider_request_ref: Mapped[str | None] = mapped_column(String(255))
    records_accepted: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_stale: Mapped[int] = mapped_column(Integer, default=0)
    replay_of: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_runs.id"))
    requested_by: Mapped[str | None] = mapped_column(String(64))
    enqueued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queue_job_id: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncStream(Base):
    __tablename__ = "sync_streams"

    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"),
                                                     primary_key=True)
    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    fence: Mapped[int] = mapped_column(BigInteger, default=0)
    lease_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_runs.id"))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    covered_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    covered_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_publish_run_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("sync_runs.id"))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    freshness_target_s: Mapped[int | None] = mapped_column(Integer)


class RawObject(Base):
    __tablename__ = "raw_objects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_runs.id", ondelete="CASCADE"))
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"))
    dataset: Mapped[str] = mapped_column(String(64))
    page_seq: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(Text, unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SyncedRecord(Base):
    __tablename__ = "synced_records"

    connection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("connections.id", ondelete="CASCADE"),
                                                     primary_key=True)
    dataset: Mapped[str] = mapped_column(String(64), primary_key=True)
    record_key: Mapped[str] = mapped_column(Text, primary_key=True)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"))
    version: Mapped[str] = mapped_column(Text)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("sync_runs.id"))
    raw_object_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("raw_objects.id"))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
