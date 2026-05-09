"""initial schema — phase 1.0 single-tenant

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-08
"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')

    op.create_table(
        "threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_threads_tenant_id", "threads", ["tenant_id"])
    op.create_index("ix_threads_tenant_updated", "threads", ["tenant_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "thread_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("threads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("citations", postgresql.JSONB(), nullable=True),
        sa.Column("sub_states", postgresql.JSONB(), nullable=True),
        sa.Column("state", sa.String(32), nullable=True),
        sa.Column("degraded", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_messages_thread_id", "messages", ["thread_id"])
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])

    op.create_table(
        "diagnostics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            unique=True,
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("final_state", sa.String(32), nullable=False),
        sa.Column("model_used", sa.String(64), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("cache_creation_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_read_input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("input_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cache_hit_rate", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_diagnostics_tenant_id", "diagnostics", ["tenant_id"])

    op.create_table(
        "reactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("emoji", sa.String(8), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("message_id", "tenant_id", name="uq_reaction_message_tenant"),
    )
    op.create_index("ix_reactions_tenant_id", "reactions", ["tenant_id"])

    op.create_table(
        "lwa_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), unique=True, nullable=False),
        sa.Column("seller_id", sa.String(64), nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "diagnostic_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("diagnostics.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_tenant_id", "audit_log", ["tenant_id"])
    op.create_index("ix_audit_diagnostic_id", "audit_log", ["diagnostic_id"])
    op.create_index("ix_audit_event_type", "audit_log", ["event_type"])
    op.create_index("ix_audit_created_at", "audit_log", ["created_at"])
    op.create_index(
        "ix_audit_tenant_event_ts", "audit_log", ["tenant_id", "event_type", "created_at"]
    )

    op.create_table(
        "memory",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column(
            "source_message_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_tenant_id", "memory", ["tenant_id"])
    op.execute(
        "CREATE INDEX ix_memory_embedding_hnsw ON memory "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_memory_embedding_hnsw", table_name="memory")
    op.drop_index("ix_memory_tenant_id", table_name="memory")
    op.drop_table("memory")

    op.drop_index("ix_audit_tenant_event_ts", table_name="audit_log")
    op.drop_index("ix_audit_created_at", table_name="audit_log")
    op.drop_index("ix_audit_event_type", table_name="audit_log")
    op.drop_index("ix_audit_diagnostic_id", table_name="audit_log")
    op.drop_index("ix_audit_tenant_id", table_name="audit_log")
    op.drop_table("audit_log")

    op.drop_table("lwa_tokens")

    op.drop_index("ix_reactions_tenant_id", table_name="reactions")
    op.drop_table("reactions")

    op.drop_index("ix_diagnostics_tenant_id", table_name="diagnostics")
    op.drop_table("diagnostics")

    op.drop_index("ix_messages_tenant_id", table_name="messages")
    op.drop_index("ix_messages_thread_id", table_name="messages")
    op.drop_table("messages")

    op.drop_index("ix_threads_tenant_updated", table_name="threads")
    op.drop_index("ix_threads_tenant_id", table_name="threads")
    op.drop_table("threads")
