import pytest
from sqlalchemy import create_engine

from jobs.db import MissingWorkspaceScope, ScopedDb


@pytest.fixture
def db() -> ScopedDb:
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("create table rows (workspace_id text, v int)")
        c.exec_driver_sql("insert into rows values ('a', 1), ('b', 2)")
        c.exec_driver_sql("create table workspaces (id text, status text)")
        c.exec_driver_sql("insert into workspaces values ('a', 'ready'), ('b', 'creating')")
    return ScopedDb(engine)


def test_scoped_query_only_sees_its_workspace(db: ScopedDb) -> None:
    rows = db.execute("select v from rows where workspace_id = :workspace_id", {"workspace_id": "a"})
    assert rows == [{"v": 1}]


@pytest.mark.parametrize(
    ("sql", "params"),
    [
        ("select v from rows", {}),
        ("select v from rows", {"workspace_id": "a"}),
        ("select v from rows where workspace_id = :workspace_id", {}),
    ],
)
def test_unscoped_queries_are_refused(db: ScopedDb, sql: str, params: dict[str, str]) -> None:
    with pytest.raises(MissingWorkspaceScope):
        db.execute(sql, params)


def test_fan_out_lists_ready_workspaces(db: ScopedDb) -> None:
    assert db.unscoped_workspaces() == [{"id": "a"}]
