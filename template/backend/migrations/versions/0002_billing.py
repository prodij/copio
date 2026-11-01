"""billing"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002"
down_revision = "0001"


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), primary_key=True),
        sa.Column("plan_code", sa.String(64), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("lago_external_id", sa.String(128), unique=True),
        sa.Column("lago_subscription_id", sa.String(128), unique=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.String(128), primary_key=True),
        sa.Column("signature_sha256", sa.String(64), unique=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("webhook_events")
    op.drop_table("subscriptions")
