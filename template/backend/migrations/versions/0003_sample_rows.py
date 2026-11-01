"""sample_rows: the processed rows of the sample_fetch job"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"


def upgrade() -> None:
    op.create_table(
        "sample_rows",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("raw_key", sa.Text(), nullable=False, unique=True),  # re-processing upserts by it
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_sample_rows_workspace_id", "sample_rows", ["workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_sample_rows_workspace_id", table_name="sample_rows")
    op.drop_table("sample_rows")
