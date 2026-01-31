"""SQLAlchemy Base class and common mixins."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, func, TypeDecorator
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class StringUUID(TypeDecorator):
    """UUID type that stores as string in database but returns UUID objects.
    
    Prisma stores UUIDs as text/varchar, so we need this adapter to work
    with the existing schema while keeping Python UUIDs.
    """
    impl = String
    cache_ok = True
    
    def process_bind_param(self, value, dialect):
        """Convert UUID to string for storage."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return str(value)
        return value
    
    def process_result_value(self, value, dialect):
        """Convert string back to UUID on retrieval."""
        if value is None:
            return None
        if isinstance(value, UUID):
            return value
        return UUID(value)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models.
    
    Note: We don't set a global UUID type mapping because the database has
    mixed column types (real UUID for tenants/users, text for Prisma tables).
    Each model should explicitly specify the type.
    """
    pass


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps (snake_case columns)."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class PrismaTimestampMixin:
    """Mixin for Prisma-style camelCase timestamp columns.
    
    Note: Prisma doesn't set server defaults for updatedAt, so we use
    Python-side defaults instead.
    """

    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        "updatedAt",
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class TenantMixin:
    """Mixin for multi-tenant models (snake_case columns)."""

    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )


class PrismaTenantMixin:
    """Mixin for Prisma-style multi-tenant models (camelCase columns)."""

    tenant_id: Mapped[UUID] = mapped_column(
        "tenantId",
        PG_UUID(as_uuid=True),
        nullable=False,
        index=True,
    )


def generate_uuid() -> UUID:
    """Generate a new UUID."""
    return uuid4()
