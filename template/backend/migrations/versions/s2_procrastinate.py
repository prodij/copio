"""procrastinate: the job queue's schema (Procrastinate 3.11.0), on the app's own Postgres

The SQL is Procrastinate's own `procrastinate/sql/schema.sql`, vendored unchanged next to the
migrations (migrations/procrastinate/schema-3.11.0.sql) because the backend image doesn't install
Procrastinate. jobs/tests/test_engine_schema.py fails if it ever differs from the installed package's
schema, so a version bump means a new vendored file and a migration that applies Procrastinate's
upgrade scripts (procrastinate/sql/migrations) in order.
"""
from pathlib import Path

from alembic import op

revision = "s2_procrastinate"
down_revision = "0004"

SCHEMA = Path(__file__).resolve().parents[1] / "procrastinate" / "schema-3.11.0.sql"

TABLES = ("procrastinate_periodic_defers", "procrastinate_events", "procrastinate_jobs",
          "procrastinate_workers")
FUNCTIONS = (
    "procrastinate_cancel_job_v1", "procrastinate_defer_jobs_v1", "procrastinate_defer_periodic_job_v2",
    "procrastinate_fetch_job_v2", "procrastinate_finish_job_v1",
    "procrastinate_notify_queue_abort_job_v1", "procrastinate_notify_queue_job_inserted_v1",
    "procrastinate_prune_stalled_workers_v1", "procrastinate_register_worker_v1",
    "procrastinate_retry_job_v1", "procrastinate_retry_job_v2",
    "procrastinate_trigger_abort_requested_events_procedure_v1",
    "procrastinate_trigger_function_scheduled_events_v1",
    "procrastinate_trigger_function_status_events_insert_v1",
    "procrastinate_trigger_function_status_events_update_v1",
    "procrastinate_unlink_periodic_defers_v1", "procrastinate_unregister_worker_v1",
    "procrastinate_update_heartbeat_v1",
)
TYPES = ("procrastinate_job_to_defer_v1", "procrastinate_job_event_type", "procrastinate_job_status")


def _run(sql: str) -> None:
    # The driver's own execute: the schema is many statements with `:=` and `%` that SQLAlchemy's
    # text() and the DB-API paramstyle would otherwise try to read as parameters.
    op.get_bind().connection.driver_connection.execute(sql)  # type: ignore[union-attr]


def upgrade() -> None:
    _run(SCHEMA.read_text())


def downgrade() -> None:
    _run("".join(f"drop table if exists {t} cascade;" for t in TABLES))
    _run("".join(f"drop function if exists {f} cascade;" for f in FUNCTIONS))
    _run("".join(f"drop type if exists {t} cascade;" for t in TYPES))
