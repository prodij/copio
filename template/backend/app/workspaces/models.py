import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Workspace(Base):
    """One customer workspace = one Zitadel organization + one Lago customer.

    `owner_user_id` is unique: milestone 1 allows one owned workspace per user, which is
    what makes `POST /workspaces` idempotent.
    """

    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    owner_user_id: Mapped[str] = mapped_column(String(64), unique=True)
    zitadel_org_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    zitadel_grant_id: Mapped[str | None] = mapped_column(String(64))
    lago_customer_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="creating")  # creating | ready
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
