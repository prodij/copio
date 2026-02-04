"""Admin audit log model for tracking superuser actions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, generate_uuid


class AdminAuditLog(Base):
    """Append-only audit log for superuser/admin actions.

    Tracks all God-mode operations with before/after state diffs.
    Separate from tenant-scoped AuditLog for security isolation.
    """

    __tablename__ = "admin_audit_log"
    __table_args__ = (
        Index("idx_admin_audit_log_admin", "admin_id", "created_at"),
        Index("idx_admin_audit_log_action", "action", "created_at"),
        Index("idx_admin_audit_log_target", "target_type", "target_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=generate_uuid
    )

    # Who performed the action (must be superuser)
    admin_id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # What action was performed
    action: Mapped[str] = mapped_column(String(100), nullable=False)

    # What was affected
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[UUID | None] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    target_label: Mapped[str] = mapped_column(String(255), nullable=False)

    # State diff
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Request context
    ip_address: Mapped[str] = mapped_column(INET, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Impersonation context (if admin was impersonating a user)
    impersonating_user_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, nullable=False
    )

    # Relationships
    admin = relationship("User", foreign_keys=[admin_id], lazy="selectin")
    impersonating_user = relationship(
        "User", foreign_keys=[impersonating_user_id], lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<AdminAuditLog {self.action} by {self.admin_id}>"
