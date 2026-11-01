"""workspaces"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("owner_user_id", sa.String(64), nullable=False, unique=True),
        sa.Column("zitadel_org_id", sa.String(64), unique=True),
        sa.Column("zitadel_grant_id", sa.String(64)),
        sa.Column("lago_customer_id", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("workspaces")
