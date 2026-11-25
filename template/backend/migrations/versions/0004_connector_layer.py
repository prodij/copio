"""connector layer: connections, credentials, schedules, runs, raw objects, streams, records, audit

Spec: docs/superpowers/specs/2026-11-25-connector-layer-design.md. Owned by the integrator; a session
that needs a schema change adds its own migration (revision "s<N>_<name>", down_revision "0004") and
the integrator puts the chain in order at merge.
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision = "0004"
down_revision = "0003"

JSONB = pg.JSONB()


def now() -> sa.TextClause:
    return sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "connections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("account_ref", sa.String(255), nullable=False),  # the provider's account/store id
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("state", sa.String(24), nullable=False, server_default="healthy"),
        sa.Column("state_reason", sa.Text()),
        sa.Column("scopes", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
        sa.UniqueConstraint("workspace_id", "provider", "account_ref"),
        sa.CheckConstraint("state in ('healthy','reconnect_needed','paused','disconnected')",
                           name="ck_connections_state"),
    )
    op.create_index("ix_connections_workspace_id", "connections", ["workspace_id"])

    op.create_table(
        "credentials",
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),  # envelope-encrypted JSON
        sa.Column("key_id", sa.String(255), nullable=False),  # which data key / KMS key wrapped it
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("refreshed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
    )

    op.create_table(
        "sync_schedules",
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("dataset", sa.String(64), primary_key=True),
        sa.Column("kind", sa.String(16), nullable=False, server_default="incremental"),
        sa.Column("cron", sa.String(64), nullable=False),  # evaluated in `timezone`, executed in UTC
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("jitter_s", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("overlap", sa.String(16), nullable=False, server_default="skip"),  # skip | queue_one
        sa.Column("catchup_window_s", sa.Integer(), nullable=False, server_default="3600"),
        sa.Column("lookback_s", sa.Integer(), nullable=False, server_default="0"),  # window overlap
        sa.Column("paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("next_due_at", sa.DateTime(timezone=True)),
        sa.Column("last_enqueued_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sync_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connector_version", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.Text(), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
        sa.Column("stage", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("checkpoint", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("wait_reason", sa.Text()),
        sa.Column("error_code", sa.String(64)),
        sa.Column("error_detail", sa.Text()),  # sanitized: never a token, never a raw payload
        sa.Column("provider_request_ref", sa.String(255)),
        sa.Column("records_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_stale", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("replay_of", sa.Uuid(), sa.ForeignKey("sync_runs.id")),
        sa.Column("requested_by", sa.String(64)),  # user id for manual runs
        # Transactional outbox: whoever creates a run (backend or scheduler) only inserts this row.
        # The dispatcher (jobs) hands rows with enqueued_at null to the queue and stamps them.
        sa.Column("enqueued_at", sa.DateTime(timezone=True)),
        sa.Column("queue_job_id", sa.BigInteger()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status in ('queued','running','waiting','succeeded','failed','cancelled')",
                           name="ck_sync_runs_status"),
        sa.CheckConstraint("kind in ('incremental','backfill','report','replay')", name="ck_sync_runs_kind"),
    )
    op.create_index("ix_sync_runs_stream", "sync_runs", ["connection_id", "dataset", "created_at"])
    op.create_index("ix_sync_runs_workspace_status", "sync_runs", ["workspace_id", "status"])
    op.create_index("ix_sync_runs_outbox", "sync_runs", ["created_at"],
                    postgresql_where=sa.text("enqueued_at is null and status = 'queued'"))

    # One row per (connection, dataset): who owns it now (lease + fence) and what is published.
    op.create_table(
        "sync_streams",
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("dataset", sa.String(64), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("fence", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("lease_run_id", sa.Uuid(), sa.ForeignKey("sync_runs.id")),
        sa.Column("lease_owner", sa.String(128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("covered_from", sa.DateTime(timezone=True)),  # published coverage, contiguous
        sa.Column("covered_to", sa.DateTime(timezone=True)),
        sa.Column("last_publish_at", sa.DateTime(timezone=True)),
        sa.Column("last_publish_run_id", sa.Uuid(), sa.ForeignKey("sync_runs.id")),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("freshness_target_s", sa.Integer()),
    )

    op.create_table(
        "raw_objects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("sync_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("dataset", sa.String(64), nullable=False),
        sa.Column("page_seq", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
        sa.Column("processed_at", sa.DateTime(timezone=True)),  # null = in the replay backlog
        sa.UniqueConstraint("run_id", "page_seq"),
    )
    op.create_index("ix_raw_objects_backlog", "raw_objects", ["connection_id", "dataset"],
                    postgresql_where=sa.text("processed_at is null"))

    # The template's generic published store. A product may also project these into its own tables.
    op.create_table(
        "synced_records",
        sa.Column("connection_id", sa.Uuid(), sa.ForeignKey("connections.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("dataset", sa.String(64), primary_key=True),
        sa.Column("record_key", sa.Text(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("data", JSONB, nullable=False),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("sync_runs.id"), nullable=False),
        sa.Column("raw_object_id", sa.Uuid(), sa.ForeignKey("raw_objects.id")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
    )
    op.create_index("ix_synced_records_workspace", "synced_records", ["workspace_id", "dataset"])

    # Provider quota buckets, keyed by the provider's own quota scope (e.g. "shopify:<store>").
    op.create_table(
        "rate_budgets",
        sa.Column("budget_key", sa.String(255), primary_key=True),
        sa.Column("capacity", sa.Float(), nullable=False),
        sa.Column("refill_per_s", sa.Float(), nullable=False),
        sa.Column("tokens", sa.Float(), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),  # from a provider 429 / Retry-After
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
    )

    # Append-only. Every operator action, connection change, and (later) every agent tool call.
    op.create_table(
        "audit_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.Uuid(), sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("actor_type", sa.String(16), nullable=False),  # user | agent | system
        sa.Column("actor_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),  # e.g. connection.pause, run.replay
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("detail", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now()),
        sa.CheckConstraint("actor_type in ('user','agent','system')", name="ck_audit_actor_type"),
    )
    op.create_index("ix_audit_events_workspace", "audit_events", ["workspace_id", "created_at"])
    op.execute("""
        create function audit_events_append_only() returns trigger language plpgsql as $$
        begin raise exception 'audit_events is append-only'; end $$;
    """)
    op.execute("""
        create trigger audit_events_no_change before update or delete on audit_events
        for each row execute function audit_events_append_only();
    """)


def downgrade() -> None:
    op.execute("drop trigger if exists audit_events_no_change on audit_events")
    op.execute("drop function if exists audit_events_append_only()")
    for table in ("audit_events", "rate_budgets", "synced_records", "raw_objects", "sync_streams",
                  "sync_runs", "sync_schedules", "credentials", "connections"):
        op.drop_table(table)
