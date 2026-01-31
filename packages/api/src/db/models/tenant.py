"""Tenant model for multi-tenancy."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from src.db.models.user import User


class Tenant(Base, TimestampMixin):
    """Tenant model for multi-tenant isolation."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles")
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"
