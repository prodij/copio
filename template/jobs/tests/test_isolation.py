"""Isolation for jobs (spec §10). ScopedDb is a guard against forgetting the workspace scope, not a
boundary: it refuses SQL without a bound `:workspace_id`, and the handlers reach the database only
through it."""

import ast
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from jobs.db import MissingWorkspaceScope, ScopedDb

HANDLERS = Path(__file__).resolve().parents[1] / "jobs" / "handlers"
# Handlers may build an engine to hand to ScopedDb, nothing more from SQLAlchemy.
ALLOWED_SQLALCHEMY = {"create_engine"}
RAW_DB_ATTRS = {"connect", "begin", "exec_driver_sql", "engine", "raw_connection"}


@pytest.fixture
def db() -> ScopedDb:
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table sample_rows (workspace_id text, v int)")
        c.exec_driver_sql("insert into sample_rows values ('ws-a', 1), ('ws-b', 2)")
    return ScopedDb(engine)


def test_workspace_a_cannot_read_workspace_b(db: ScopedDb) -> None:
    sql = "select v from sample_rows where workspace_id = :workspace_id"
    assert db.execute(sql, {"workspace_id": "ws-a"}) == [{"v": 1}]
    assert db.execute(sql, {"workspace_id": "ws-missing"}) == []


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ("select v from sample_rows", {}),
        ("select v from sample_rows", {"workspace_id": "ws-a"}),
        ("select v from sample_rows where workspace_id = :workspace_id", {}),
        ("select v from sample_rows where workspace_id = :workspace_id", {"workspace_id": ""}),
    ],
)
def test_a_query_without_a_bound_workspace_is_refused(db: ScopedDb, sql: str, params: dict[str, str]) -> None:
    with pytest.raises(MissingWorkspaceScope):
        db.execute(sql, params)


@pytest.mark.parametrize("path", sorted(HANDLERS.glob("*.py")), ids=lambda p: p.name)
def test_handlers_use_the_database_only_through_scoped_db(path: Path) -> None:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {a.name for a in node.names if a.name.split(".")[0] == "sqlalchemy"}
        elif isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "sqlalchemy":
            found |= {a.name for a in node.names} - ALLOWED_SQLALCHEMY
        elif isinstance(node, ast.Attribute) and node.attr in RAW_DB_ATTRS:
            found.add(node.attr)
    assert not found, f"{path.name} uses {sorted(found)}; go through ScopedDb"
