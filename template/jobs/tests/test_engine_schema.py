"""The queue schema the backend's migration applies is exactly the installed Procrastinate's."""

import importlib.metadata
import importlib.resources
import pathlib

from sqlalchemy import Engine, text

MIGRATIONS = pathlib.Path(__file__).resolve().parents[2] / "backend" / "migrations"


def test_vendored_schema_matches_the_installed_procrastinate() -> None:
    version = importlib.metadata.version("procrastinate")
    vendored = MIGRATIONS / "procrastinate" / f"schema-{version}.sql"
    assert vendored.exists(), (
        f"Procrastinate {version} is installed but {vendored.name} is not vendored: add it and a migration "
        "that applies Procrastinate's upgrade scripts from the previous version")
    shipped = importlib.resources.files("procrastinate").joinpath("sql/schema.sql").read_text()
    assert vendored.read_text() == shipped


def test_migration_follows_the_contract_migration() -> None:
    source = (MIGRATIONS / "versions" / "s2_procrastinate.py").read_text()
    assert 'revision = "s2_procrastinate"' in source and 'down_revision = "s1_ledger_receipts"' in source  # linearized


def test_queue_tables_exist_next_to_the_connector_tables(pg_engine: Engine) -> None:
    with pg_engine.connect() as conn:
        tables = set(conn.execute(text(
            "select tablename from pg_tables where schemaname = 'public'")).scalars())
    assert {"procrastinate_jobs", "procrastinate_workers", "procrastinate_periodic_defers",
            "sync_runs", "sync_schedules", "rate_budgets"} <= tables
