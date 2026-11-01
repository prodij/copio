import importlib
from datetime import UTC, datetime

from jobs.scheduler import Schedule, due, load_schedules


def test_due_runs_once_per_slot() -> None:
    s = [Schedule("billing_reconcile", "*/15 * * * *")]
    now = datetime(2026, 10, 31, 12, 15, 5, tzinfo=UTC)
    assert due(s, now, {}) == ["billing_reconcile"]
    assert due(s, now, {"billing_reconcile": datetime(2026, 10, 31, 12, 15, 1, tzinfo=UTC)}) == []
    assert due(s, now, {"billing_reconcile": datetime(2026, 10, 31, 12, 0, 1, tzinfo=UTC)}) == ["billing_reconcile"]


def test_shipped_schedules_name_real_handlers() -> None:
    schedules = load_schedules()
    assert schedules == [Schedule("billing_reconcile", "*/15 * * * *"), Schedule("sample_fetch", "0 * * * *")]
    for s in schedules:
        module = importlib.import_module(f"jobs.handlers.{s.name}")
        assert callable(module.handler)
