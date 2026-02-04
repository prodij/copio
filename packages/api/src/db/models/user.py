"""User model with fastapi-users integration."""

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from src.db.models.tenant import Tenant
    from src.db.models.user_role import UserRole
    from src.db.models.role import Role


class User(SQLAlchemyBaseUserTableUUID, Base, TimestampMixin):
    """User model with tenant association and roles."""

    __tablename__ = "users"

    # Tenant association
    tenant_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )

    # User profile
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), default="member")  # 'admin' | 'member'

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="users")
    user_roles: Mapped[list["UserRole"]] = relationship("UserRole", back_populates="user", lazy="selectin")
    
    # Direct relationship to roles (many-to-many via user_roles)
    roles: Mapped[list["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        viewonly=True,
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User {self.email}>"

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or self.email
