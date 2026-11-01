import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Subscription(Base):
    """One per workspace.

    `lago_external_id` is this checkout attempt's external id in Lago (`{workspace}:{plan}:{8 hex}`),
    saved before Lago is asked to create the subscription and new on every restart, so webhooks for
    an earlier attempt match nothing. `lago_subscription_id` stays null until the Lago subscription
    exists, then holds the same value.
    """

    __tablename__ = "subscriptions"

    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspaces.id"), primary_key=True)
    plan_code: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(16))  # pending | active | past_due | canceled
    lago_external_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    lago_subscription_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # X-Lago-Unique-Key
    signature_sha256: Mapped[str | None] = mapped_column(String(64), unique=True)  # of X-Lago-Signature
    type: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
