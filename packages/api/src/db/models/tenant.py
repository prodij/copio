"""Tenant model for multi-tenancy."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.role import Role
    from src.db.models.api_key import ApiKey


class Tenant(Base, TimestampMixin):
    """Tenant model for multi-tenant isolation."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="America/Los_Angeles")
    base_currency: Mapped[str] = mapped_column(String(3), default="USD")
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Company identity
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Address
    address_line1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str | None] = mapped_column(String(2), default="US")
    
    # Contact
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Branding
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Onboarding status
    onboarding_complete: Mapped[bool] = mapped_column(default=False, server_default="false")

    # Status management
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active", nullable=False
    )
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")
    roles: Mapped[list["Role"]] = relationship("Role", back_populates="tenant")
    api_keys: Mapped[list["ApiKey"]] = relationship(
        "ApiKey",
        back_populates="tenant",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Tenant {self.slug}>"
