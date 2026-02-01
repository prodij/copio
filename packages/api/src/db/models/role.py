"""Role model for dynamic RBAC."""

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid

if TYPE_CHECKING:
    from src.db.models.tenant import Tenant
    from src.db.models.user_role import UserRole


class Role(Base, TimestampMixin):
    """Role with customizable permissions per tenant."""

    __tablename__ = "roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_name"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_system: Mapped[bool] = mapped_column(default=False)
    permissions: Mapped[list] = mapped_column(JSONB, default=list)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="roles")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="role")

    def __repr__(self) -> str:
        return f"<Role {self.name}>"
