"""The sync scheduler: pure slot arithmetic, then the database behavior on real Postgres."""

import threading
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text

from jobs.sync.contract import Window
from jobs.sync.scheduler import (
    Schedule,
    Scheduler,
    jitter_for,
    next_due,
    plan,
    slot_after,
    slot_at_or_before,
)


def utc(*args: int) -> datetime:
    return datetime(*args, tzinfo=UTC)  # type: ignore[misc]


def sched(cron: str = "0 * * * *", *, tz: str = "UTC", jitter_s: int = 0, catchup_window_s: int = 3600,
          lookback_s: int = 0, next_due_at: datetime | None = None, overlap: str = "skip") -> Schedule:
    return Schedule(uuid.UUID(int=1), "orders", "incremental", cron, tz, jitter_s, overlap,
                    catchup_window_s, lookback_s, next_due_at)


# -- pure ------------------------------------------------------------------------------------------


def test_cron_is_evaluated_in_the_schedules_timezone_across_dst() -> None:
    berlin = "Europe/Berlin"
    # 02:30 local every day: 01:30 UTC in winter (CET), 00:30 UTC in summer (CEST, from 29 March 2026).
    assert slot_after("30 2 * * *", berlin, utc(2026, 3, 27, 12)) == utc(2026, 3, 28, 1, 30)
    assert slot_after("30 2 * * *", berlin, utc(2026, 3, 30, 12)) == utc(2026, 3, 31, 0, 30)
    assert slot_at_or_before("0 9 * * *", "America/New_York", utc(2026, 7, 1, 13)) == utc(2026, 7, 1, 13)
    assert slot_at_or_before("0 9 * * *", "America/New_York", utc(2026, 12, 1, 13)) == utc(2026, 11, 30, 14)


def test_a_due_slot_runs_the_window_since_the_previous_slot_with_lookback() -> None:
    p = plan(sched(lookback_s=600, next_due_at=utc(2026, 11, 25, 12)), utc(2026, 11, 25, 12, 0, 20))
    assert p.window == Window(utc(2026, 11, 25, 10, 50), utc(2026, 11, 25, 12))
    assert p.next_due_at == utc(2026, 11, 25, 13)
    assert p.reason == "due"


def test_a_new_schedule_runs_the_slot_that_just_passed() -> None:
    p = plan(sched(), utc(2026, 11, 25, 12, 40))
    assert p.window == Window(utc(2026, 11, 25, 11), utc(2026, 11, 25, 12))


def test_missed_slots_inside_the_catchup_window_become_one_run() -> None:
    # Down from 09:00 until 12:20; the catch-up window is two hours (from 10:20).
    p = plan(sched(catchup_window_s=7200, next_due_at=utc(2026, 11, 25, 9)), utc(2026, 11, 25, 12, 20))
    assert p.window == Window(utc(2026, 11, 25, 10), utc(2026, 11, 25, 12))  # slots 11:00 and 12:00
    assert p.reason == "catch-up"
    assert p.next_due_at == utc(2026, 11, 25, 13)


def test_missed_slots_older_than_the_catchup_window_create_nothing() -> None:
    p = plan(sched(catchup_window_s=600, next_due_at=utc(2026, 11, 25, 9)), utc(2026, 11, 25, 12, 20))
    assert p.window is None
    assert p.next_due_at == utc(2026, 11, 25, 13)


def test_jitter_is_deterministic_bounded_and_spread() -> None:
    slot = utc(2026, 11, 25, 12)
    s = sched(jitter_s=300)
    assert jitter_for(s, slot) == jitter_for(s, slot)
    offsets = {jitter_for(Schedule(uuid.UUID(int=i), "orders", "incremental", "0 * * * *", "UTC", 300,
                                   "skip", 3600, 0, None), slot) for i in range(50)}
    assert all(timedelta(0) <= o <= timedelta(seconds=300) for o in offsets)
    assert len(offsets) > 20
    # Never as long as the period, so a jittered due time still names its slot.
    every_minute = sched("* * * * *", jitter_s=3600)
    assert all(jitter_for(every_minute, slot + timedelta(minutes=m)) < timedelta(minutes=1) for m in range(50))


def test_a_jittered_due_time_plans_its_own_slot() -> None:
    s = sched(jitter_s=900)
    due = next_due(s, utc(2026, 11, 25, 11, 30))
    assert utc(2026, 11, 25, 12) <= due <= utc(2026, 11, 25, 12, 15)
    p = plan(sched(jitter_s=900, next_due_at=due), due)
    assert p.window == Window(utc(2026, 11, 25, 11), utc(2026, 11, 25, 12))


# -- database --------------------------------------------------------------------------------------

NOW = utc(2026, 11, 25, 12, 0, 30)


def add_connection(db: Engine, workspace_id: str, state: str = "healthy") -> uuid.UUID:
    cid = uuid.uuid4()
    with db.begin() as conn:
        conn.execute(text(
            "insert into connections (id, workspace_id, provider, account_ref, display_name, state)"
            " values (:id, :ws, 'synthetic', :ref, 'Synthetic', :state)"),
            {"id": cid, "ws": workspace_id, "ref": f"acct-{cid}", "state": state})
    return cid


def add_schedule(db: Engine, connection_id: uuid.UUID, dataset: str = "orders", **cols: Any) -> None:
    values = {"kind": "incremental", "cron": "0 * * * *", "timezone": "UTC", "jitter_s": 0,
              "overlap": "skip", "catchup_window_s": 3600, "lookback_s": 0, "paused": False,
              "next_due_at": utc(2026, 11, 25, 12), **cols}
    with db.begin() as conn:
        conn.execute(text(
            "insert into sync_schedules (connection_id, dataset, kind, cron, timezone, jitter_s, overlap,"
            " catchup_window_s, lookback_s, paused, next_due_at)"
            " values (:connection_id, :dataset, :kind, :cron, :timezone, :jitter_s, :overlap,"
            " :catchup_window_s, :lookback_s, :paused, :next_due_at)"),
            {"connection_id": connection_id, "dataset": dataset, **values})


def runs(db: Engine) -> list[dict[str, Any]]:
    with db.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(
            "select connection_id, dataset, kind, trigger, status, window_start, window_end, enqueued_at,"
            " connector_version from sync_runs order by created_at"))]


def schedule_row(db: Engine, connection_id: uuid.UUID, dataset: str = "orders") -> dict[str, Any]:
    with db.connect() as conn:
        return dict(conn.execute(text("select * from sync_schedules where connection_id = :c and dataset = :d"),
                                 {"c": connection_id, "d": dataset}).one()._mapping)


def test_tick_creates_outbox_rows_only(clean_tables: Engine, two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, lookback_s=300)
    result = Scheduler(clean_tables, connector_version=lambda p: f"{p}@2").tick(NOW)
    assert len(result.created) == 1
    [run] = runs(clean_tables)
    assert run == {"connection_id": cid, "dataset": "orders", "kind": "incremental", "trigger": "schedule",
                   "status": "queued", "window_start": utc(2026, 11, 25, 10, 55),
                   "window_end": utc(2026, 11, 25, 12), "enqueued_at": None,
                   "connector_version": "synthetic@2"}
    row = schedule_row(clean_tables, cid)
    assert row["next_due_at"] == utc(2026, 11, 25, 13) and row["last_enqueued_at"] == NOW
    assert Scheduler(clean_tables).tick(NOW).created == []  # not due again until 13:00


def test_two_schedulers_at_once_create_each_run_once(clean_tables: Engine,
                                                     two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    for i in range(30):
        add_schedule(clean_tables, cid, dataset=f"d{i}")
    schedulers = [Scheduler(clean_tables, batch=4) for _ in range(3)]
    barrier = threading.Barrier(len(schedulers))
    created: list[uuid.UUID] = []

    def go(s: Scheduler) -> None:
        barrier.wait()
        for _ in range(15):  # several ticks each, all at the same instant
            created.extend(s.tick(NOW).created)

    threads = [threading.Thread(target=go, args=(s,)) for s in schedulers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(created) == 30
    assert sorted(r["dataset"] for r in runs(clean_tables)) == sorted(f"d{i}" for i in range(30))


def test_missed_runs_are_caught_up_once(clean_tables: Engine, two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, next_due_at=utc(2026, 11, 25, 8), catchup_window_s=3 * 3600)
    result = Scheduler(clean_tables).tick(NOW)  # back up at 12:00:30, four slots missed
    assert len(result.created) == 1
    [run] = runs(clean_tables)
    assert (run["window_start"], run["window_end"]) == (utc(2026, 11, 25, 9), utc(2026, 11, 25, 12))
    assert schedule_row(clean_tables, cid)["next_due_at"] == utc(2026, 11, 25, 13)


def test_overlap_skip_creates_nothing_while_a_run_is_active(clean_tables: Engine,
                                                           two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, next_due_at=utc(2026, 11, 25, 11))
    scheduler = Scheduler(clean_tables)
    assert len(scheduler.tick(utc(2026, 11, 25, 11, 0, 5)).created) == 1
    with clean_tables.begin() as conn:
        conn.execute(text("update sync_runs set status = 'running'"))
    result = scheduler.tick(NOW)
    assert result.created == [] and result.skipped == [(cid, "orders", "overlap: a run is active")]
    assert schedule_row(clean_tables, cid)["next_due_at"] == utc(2026, 11, 25, 13)  # moved on anyway
    with clean_tables.begin() as conn:
        conn.execute(text("update sync_runs set status = 'succeeded'"))
    assert len(scheduler.tick(utc(2026, 11, 25, 13, 0, 1)).created) == 1


def test_overlap_queue_one_allows_one_queued_behind_a_running_run(clean_tables: Engine,
                                                                 two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, overlap="queue_one", next_due_at=utc(2026, 11, 25, 11))
    scheduler = Scheduler(clean_tables)
    scheduler.tick(utc(2026, 11, 25, 11, 0, 5))
    with clean_tables.begin() as conn:
        conn.execute(text("update sync_runs set status = 'running'"))
    assert len(scheduler.tick(NOW).created) == 1  # one queued behind the running one
    result = scheduler.tick(utc(2026, 11, 25, 13, 0, 1))
    assert result.created == [] and result.skipped == [(cid, "orders", "overlap: a run is already queued")]
    assert [r["status"] for r in runs(clean_tables)] == ["running", "queued"]


@pytest.mark.parametrize("state", ["paused", "reconnect_needed", "disconnected"])
def test_connections_that_are_not_healthy_get_no_runs(clean_tables: Engine, two_workspaces: tuple[str, str],
                                                      state: str) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws, state=state)
    add_schedule(clean_tables, cid)
    assert Scheduler(clean_tables).tick(NOW).created == []
    assert runs(clean_tables) == []
    assert schedule_row(clean_tables, cid)["next_due_at"] == utc(2026, 11, 25, 12)  # untouched


def test_a_paused_schedule_gets_no_runs_and_resumes_without_a_backlog(clean_tables: Engine,
                                                                      two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, paused=True, next_due_at=utc(2026, 11, 25, 6))
    scheduler = Scheduler(clean_tables)
    assert scheduler.tick(NOW).created == []
    with clean_tables.begin() as conn:
        conn.execute(text("update sync_schedules set paused = false"))
    # Unpaused at 12:00:30: only the catch-up window (one hour) is run, not six hours of slots.
    scheduler.tick(NOW)
    [run] = runs(clean_tables)
    assert (run["window_start"], run["window_end"]) == (utc(2026, 11, 25, 11), utc(2026, 11, 25, 12))


def test_an_invalid_schedule_is_skipped_without_stopping_the_others(clean_tables: Engine,
                                                                    two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    cid = add_connection(clean_tables, ws)
    add_schedule(clean_tables, cid, dataset="bad", cron="not a cron")
    add_schedule(clean_tables, cid, dataset="good")
    result = Scheduler(clean_tables).tick(NOW)
    assert [r["dataset"] for r in runs(clean_tables)] == ["good"]
    assert (cid, "bad", "invalid schedule") in result.skipped
