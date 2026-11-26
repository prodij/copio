"""The worker entrypoint: schedules.yaml jobs as Procrastinate periodic tasks, and the run executor hook."""

import importlib
import importlib.util
import sys
import types
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from sqlalchemy import Engine, text

from jobs import worker
from jobs.sync.engine import MAINTENANCE_QUEUE, ExecutorMissing


@pytest.fixture(autouse=True)
def no_executor() -> Iterator[None]:
    worker.install_executor(None)
    yield
    worker.install_executor(None)


def test_shipped_schedules_name_real_handlers() -> None:
    schedules = worker.load_schedules()
    assert schedules == [worker.PeriodicJob("billing_reconcile", "*/15 * * * *"),
                         worker.PeriodicJob("sample_fetch", "0 * * * *")]
    for s in schedules:
        module = importlib.import_module(f"jobs.handlers.{s.name}")
        assert callable(module.handler)


def test_schedules_become_periodic_tasks_on_the_maintenance_queue() -> None:
    engine = worker.build("postgresql+psycopg://u:p@127.0.0.1:1/none")  # nothing connects here
    periodic = {(t.task.name, t.cron) for t in engine.app.periodic_registry.periodic_tasks.values()}
    assert {("periodic.billing_reconcile", "*/15 * * * *"), ("periodic.sample_fetch", "0 * * * *"),
            ("sync.retry_stalled_jobs", "* * * * *")} <= periodic
    for name in ("periodic.billing_reconcile", "periodic.sample_fetch"):
        task = engine.app.tasks[name]
        assert task.queue == MAINTENANCE_QUEUE
        assert task.queueing_lock == name  # a slow run never piles up copies of itself


def test_a_periodic_job_runs_its_handler(pg_url: str, clean_tables: Engine,
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    def fake_handler(name: str, event: dict[str, Any]) -> dict[str, Any]:
        calls.append((name, event))
        return {"ok": True}

    monkeypatch.setattr(worker, "run_handler", fake_handler)
    engine = worker.build(pg_url, schedules=[worker.PeriodicJob("sample_fetch", "0 0 1 1 *")])  # never recently due: only our defer runs
    try:
        with engine.app.open():
            engine.app.configure_task("periodic.sample_fetch").defer(timestamp=1_764_072_000)
        engine.run_worker(queues=[MAINTENANCE_QUEUE], until_idle=True)
        assert calls == [("sample_fetch", {})]
    finally:
        with clean_tables.begin() as conn:
            conn.execute(text("truncate procrastinate_jobs, procrastinate_events, procrastinate_workers cascade"))


def test_run_executor_needs_an_installed_executor() -> None:
    with pytest.raises(ExecutorMissing):
        worker.run_executor(uuid.uuid4())
    seen: list[uuid.UUID] = []
    worker.install_executor(seen.append)
    run_id = uuid.uuid4()
    worker.run_executor(run_id)
    assert seen == [run_id]


def test_load_executor_calls_the_named_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("fake_runner")
    marker: list[uuid.UUID] = []
    module.build_executor = lambda: marker.append  # type: ignore[attr-defined]
    module.other = lambda: marker.append  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "fake_runner", module)
    executor = worker.load_executor("fake_runner")
    assert executor is not None
    monkeypatch.setenv("SYNC_EXECUTOR", "fake_runner:other")
    assert worker.load_executor() is not None
    monkeypatch.setenv("SYNC_EXECUTOR", "no_such_module:build_executor")
    with pytest.raises(ModuleNotFoundError):
        worker.load_executor()  # a named executor that is missing is a startup error, not a no-op


def test_default_executor_is_absent_until_the_runner_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SYNC_EXECUTOR", raising=False)
    runner = importlib.util.find_spec("jobs.sync.runner")
    if runner is None or not hasattr(importlib.import_module("jobs.sync.runner"), "build_executor"):
        assert worker.load_executor() is None
    else:
        assert callable(worker.load_executor())
