import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine

import doctor

NOW = datetime.now(UTC)
OLD = NOW - timedelta(days=2)


def database(tmp_path: pathlib.Path, *rows: tuple[str, dict[str, object]]) -> str:
    url = f"sqlite:///{tmp_path / 'app.db'}"
    engine = create_engine(url)
    doctor.meta.create_all(engine)
    tables = {t.name: t for t in doctor.meta.sorted_tables}
    with engine.begin() as conn:
        for table, values in rows:
            conn.execute(tables[table].insert().values(**values))
    engine.dispose()
    return url


def test_clean_database_exits_0(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    url = database(
        tmp_path,
        ("workspaces", {"id": "w1", "name": "Acme", "status": "ready", "created_at": OLD}),
        ("workspaces", {"id": "w2", "name": "New", "status": "creating", "created_at": NOW}),
        ("subscriptions", {"workspace_id": "w1", "plan_code": "starter", "state": "active", "updated_at": OLD}),
        ("subscriptions", {"workspace_id": "w2", "plan_code": "starter", "state": "pending", "updated_at": NOW}),
        ("webhook_events", {"id": "e1", "type": "invoice.created", "received_at": OLD, "processed_at": OLD}),
    )
    assert doctor.main(url) == 0
    assert "nothing stuck" in capsys.readouterr().out


def test_each_problem_is_listed_and_exits_1(tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]) -> None:
    url = database(
        tmp_path,
        ("workspaces", {"id": "w1", "name": "Acme", "status": "creating", "created_at": OLD}),
        ("subscriptions", {"workspace_id": "w1", "plan_code": "starter", "state": "pending", "updated_at": OLD}),
        ("webhook_events", {"id": "e1", "type": "invoice.created", "received_at": OLD, "processed_at": None}),
    )
    assert doctor.main(url) == 1
    out = capsys.readouterr().out
    assert "workspace w1 (Acme) stuck in 'creating'" in out
    assert "subscription of workspace w1 (starter) pending" in out
    assert "webhook e1 (invoice.created)" in out
    assert "3 problem(s)" in out


def test_unreachable_database_is_reported_without_traceback(
    tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert doctor.main(f"sqlite:///{tmp_path / 'empty.db'}") == 2  # no tables: migrations never ran
    assert "make migrate" in capsys.readouterr().err
