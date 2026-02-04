"""System settings model for global configuration."""

from uuid import UUID

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.db.base import Base, TimestampMixin, generate_uuid


class SystemSettings(Base, TimestampMixin):
    """Global system settings accessible only to superusers.

    Stores key-value configuration that applies system-wide,
    such as email verification requirements.
    """

    __tablename__ = "system_settings"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    key: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
    )
    value: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<SystemSettings {self.key}>"
