"""Shared Postgres fixtures for the connector layer's tests.

The schema comes from the real Alembic migrations in ../backend, so jobs tests run against exactly what
production runs. The database is TEST_JOBS_DATABASE_URL (default: app_jobs_test next to the backend's
app_test), created if missing and rebuilt once per test session. Tests that don't ask for `pg_engine`
need no database.
"""

import os
import pathlib
import subprocess
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

BACKEND = pathlib.Path(__file__).resolve().parents[2] / "backend"
DEFAULT_URL = "postgresql+psycopg://app:app@127.0.0.1:5432/app_jobs_test"


def jobs_database_url() -> str:
    if url := os.environ.get("TEST_JOBS_DATABASE_URL"):
        return url
    if base := os.environ.get("TEST_DATABASE_URL"):
        return make_url(base).set(database="app_jobs_test").render_as_string(hide_password=False)
    return DEFAULT_URL


def _recreate(url: str) -> None:
    target = make_url(url)
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'drop database if exists "{target.database}" with (force)'))
        conn.execute(text(f'create database "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session")
def pg_url() -> str:
    url = jobs_database_url()
    _recreate(url)
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(["uv", "run", "alembic", "upgrade", "head"], cwd=BACKEND, env=env,  # noqa: S607
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"migrations failed:\n{result.stdout}\n{result.stderr}"
    return url


@pytest.fixture(scope="session")
def pg_engine(pg_url: str) -> Iterator[Engine]:
    engine = create_engine(pg_url)
    yield engine
    engine.dispose()


@pytest.fixture
def two_workspaces(clean_tables: Engine) -> tuple[str, str]:
    """Two ready synthetic workspaces (ids as strings). Tables are emptied after the test."""
    ids = []
    with clean_tables.begin() as conn:
        for name in ("synthetic-a", "synthetic-b"):
            row = conn.execute(text(
                "insert into workspaces (id, name, owner_user_id, status, created_at)"
                " values (gen_random_uuid(), :name, :owner, 'ready', now()) returning id"),
                {"name": name, "owner": f"owner-{name}"}).one()
            ids.append(str(row.id))
    return ids[0], ids[1]


@pytest.fixture
def clean_tables(pg_engine: Engine) -> Iterator[Engine]:
    """Empties the connector tables after the test (audit_events refuses delete, so it is truncated)."""
    yield pg_engine
    with pg_engine.begin() as conn:
        conn.execute(text(
            "truncate audit_events, synced_records, raw_objects, sync_streams, sync_runs, sync_schedules,"
            " rate_budgets, credentials, connections, workspaces,"
            " procrastinate_jobs, procrastinate_events, procrastinate_periodic_defers,"
            " procrastinate_workers cascade"))
