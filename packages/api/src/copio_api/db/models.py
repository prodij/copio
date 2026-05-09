from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class Base(DeclarativeBase):
    pass


class DiagnosticState(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    TOOL_CALLS = "TOOL_CALLS"
    REASONING = "REASONING"
    DRAFTING = "DRAFTING"
    STREAMING = "STREAMING"
    COMPLETE = "COMPLETE"
    DEGRADED = "DEGRADED"
    FAILED_INTERNAL = "FAILED_INTERNAL"
    FAILED_NO_DATA = "FAILED_NO_DATA"


class Thread(Base):
    __tablename__ = "threads"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    messages: Mapped[list["Message"]] = relationship(
        back_populates="thread", cascade="all, delete-orphan", order_by="Message.created_at"
    )

    __table_args__ = (
        Index("ix_threads_tenant_updated", "tenant_id", "updated_at"),
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    thread_id: Mapped[UUID] = mapped_column(ForeignKey("threads.id", ondelete="CASCADE"), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))  # 'user' | 'assistant'
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    sub_states: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    state: Mapped[str | None] = mapped_column(String(32), nullable=True)
    degraded: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    thread: Mapped[Thread] = relationship(back_populates="messages")
    diagnostic: Mapped["Diagnostic | None"] = relationship(
        back_populates="message", uselist=False, cascade="all, delete-orphan"
    )
    reactions: Mapped[list["Reaction"]] = relationship(
        back_populates="message", cascade="all, delete-orphan"
    )


class Diagnostic(Base):
    __tablename__ = "diagnostics"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"), unique=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    question: Mapped[str] = mapped_column(Text)
    final_state: Mapped[str] = mapped_column(String(32))
    model_used: Mapped[str | None] = mapped_column(String(64), nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cache_creation_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cache_read_input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cache_hit_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )

    message: Mapped[Message] = relationship(back_populates="diagnostic")


class Reaction(Base):
    __tablename__ = "reactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    message_id: Mapped[UUID] = mapped_column(ForeignKey("messages.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    emoji: Mapped[str] = mapped_column(String(8))  # one of 👍 👎 🎯 ❓ 🔁
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )

    message: Mapped[Message] = relationship(back_populates="reactions")

    __table_args__ = (
        UniqueConstraint("message_id", "tenant_id", name="uq_reaction_message_tenant"),
    )


class LWAToken(Base):
    __tablename__ = "lwa_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True)
    seller_id: Mapped[str] = mapped_column(String(64))
    refresh_token: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    diagnostic_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("diagnostics.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), index=True
    )

    __table_args__ = (
        Index("ix_audit_tenant_event_ts", "tenant_id", "event_type", "created_at"),
    )


class MemoryRecord(Base):
    __tablename__ = "memory"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), index=True)
    kind: Mapped[str] = mapped_column(String(32))  # 'preference' | 'fact' | 'decision' | 'note'
    body: Mapped[str] = mapped_column(Text)
    source_message_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"), nullable=True
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now()
    )
