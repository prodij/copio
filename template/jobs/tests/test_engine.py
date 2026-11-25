"""ProcrastinateEngine and the dispatcher on real Postgres (the 0004 tables plus Procrastinate's schema)."""

import asyncio
import threading
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text

from jobs.sync.dispatcher import Dispatcher
from jobs.sync.engine import (
    BACKFILL_QUEUE,
    RETRY_STALLED_TASK,
    RUN_TASK,
    SYNC_QUEUE,
    ProcrastinateEngine,
    conninfo,
    stream_lock,
)

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


@pytest.fixture
def db(clean_tables: Engine) -> Iterator[Engine]:
    """clean_tables, plus an empty queue afterwards (conftest's truncate doesn't know Procrastinate)."""
    yield clean_tables
    with clean_tables.begin() as conn:
        conn.execute(text("truncate procrastinate_jobs, procrastinate_events, procrastinate_periodic_defers,"
                          " procrastinate_workers cascade"))


class Recorder:
    def __init__(self) -> None:
        self.calls: list[uuid.UUID] = []
        self.lock = threading.Lock()

    def __call__(self, run_id: uuid.UUID) -> None:
        with self.lock:
            self.calls.append(run_id)


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def engine(db: Engine, pg_url: str, recorder: Recorder) -> ProcrastinateEngine:
    return ProcrastinateEngine(pg_url, executor=recorder, db=db)


def make_connection(db: Engine, workspace_id: str, state: str = "healthy") -> uuid.UUID:
    cid = uuid.uuid4()
    with db.begin() as conn:
        conn.execute(text(
            "insert into connections (id, workspace_id, provider, account_ref, display_name, state)"
            " values (:id, :ws, 'synthetic', :ref, 'Synthetic', :state)"),
            {"id": cid, "ws": workspace_id, "ref": f"acct-{cid}", "state": state})
    return cid


def make_run(db: Engine, workspace_id: str, connection_id: uuid.UUID, *, dataset: str = "orders",
             kind: str = "incremental", status: str = "queued", hour: int = 0) -> uuid.UUID:
    rid = uuid.uuid4()
    start = T0 + timedelta(hours=hour)
    with db.begin() as conn:
        conn.execute(text(
            "insert into sync_runs (id, workspace_id, connection_id, dataset, kind, trigger, window_start,"
            " window_end, connector_version, dedupe_key, status)"
            " values (:id, :ws, :c, :d, :k, 'manual', :s, :e, 'synthetic@1', :key, :status)"),
            {"id": rid, "ws": workspace_id, "c": connection_id, "d": dataset, "k": kind, "s": start,
             "e": start + timedelta(hours=1), "key": f"{rid}", "status": status})
    return rid


def jobs(db: Engine) -> list[dict[str, Any]]:
    with db.connect() as conn:
        return [dict(r._mapping) for r in conn.execute(text(
            "select id, queue_name, task_name, lock, priority, args, status::text as status, scheduled_at"
            " from procrastinate_jobs where task_name = :t order by id"), {"t": RUN_TASK})]


def run_row(db: Engine, run_id: uuid.UUID) -> dict[str, Any]:
    with db.connect() as conn:
        return dict(conn.execute(text("select * from sync_runs where id = :id"), {"id": run_id}).one()._mapping)


def fetch(db: Engine, queues: list[str]) -> dict[str, Any] | None:
    """What a worker listening on `queues` would pick next (Procrastinate's own fetch function)."""
    with db.begin() as conn:
        row = conn.execute(text("select * from procrastinate_fetch_job_v2(:q, null)"), {"q": queues}).one()
    return None if row.id is None else dict(row._mapping)


def finish(db: Engine, job_id: int) -> None:
    with db.begin() as conn:
        conn.execute(text("select procrastinate_finish_job_v1(:id, 'succeeded', false)"), {"id": job_id})


# -- dispatch ----------------------------------------------------------------------------------------


def test_conninfo_drops_the_sqlalchemy_driver() -> None:
    assert conninfo("postgresql+psycopg://app:pw@db:5432/app?sslmode=require") == \
        "postgresql://app:pw@db:5432/app?sslmode=require"


def test_dispatch_queues_the_run_id_only_and_stamps_the_row(engine: ProcrastinateEngine, db: Engine,
                                                           two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    incremental = make_run(db, ws, conn_id)
    backfill = make_run(db, ws, conn_id, kind="backfill", hour=1)
    result = Dispatcher(engine).dispatch()
    assert set(result.new) == {incremental, backfill} and result.resumed == []
    by_run = {j["args"]["run_id"]: j for j in jobs(db)}
    assert set(by_run) == {str(incremental), str(backfill)}
    for run_id, queue, priority in ((incremental, SYNC_QUEUE, 10), (backfill, BACKFILL_QUEUE, 0)):
        job = by_run[str(run_id)]
        assert job["args"] == {"run_id": str(run_id)}  # nothing else, ever
        assert (job["queue_name"], job["priority"]) == (queue, priority)
        assert job["lock"] == stream_lock(conn_id, "orders")
        row = run_row(db, run_id)
        assert row["enqueued_at"] is not None and row["queue_job_id"] == job["id"]
        assert row["status"] == "queued"  # the runner moves it to running, not the dispatcher


def test_dispatching_twice_queues_once(engine: ProcrastinateEngine, db: Engine,
                                       two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    run_id = make_run(db, ws, conn_id)
    dispatcher = Dispatcher(engine)
    assert dispatcher.dispatch().new == [run_id]
    assert dispatcher.dispatch().total == 0
    engine.enqueue(run_id)  # the Engine protocol's enqueue is just as idempotent
    assert len(jobs(db)) == 1


def test_concurrent_dispatchers_queue_each_run_once(engine: ProcrastinateEngine, db: Engine,
                                                     two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    runs = {make_run(db, ws, conn_id, dataset=f"d{i}") for i in range(40)}
    dispatchers = [Dispatcher(engine, batch=7) for _ in range(4)]
    barrier = threading.Barrier(len(dispatchers))
    counts: list[int] = []

    def go(d: Dispatcher) -> None:
        barrier.wait()
        counts.append(d.drain())

    threads = [threading.Thread(target=go, args=(d,)) for d in dispatchers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sum(counts) == 40
    queued = [j["args"]["run_id"] for j in jobs(db)]
    assert sorted(queued) == sorted(str(r) for r in runs)  # every run once, none twice


def test_only_outbox_rows_are_dispatched(engine: ProcrastinateEngine, db: Engine,
                                         two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    for status in ("running", "succeeded", "failed", "cancelled"):
        make_run(db, ws, conn_id, status=status, dataset=status)
    assert Dispatcher(engine).dispatch().total == 0
    assert jobs(db) == []


def test_a_rolled_back_dispatch_leaves_the_row_in_the_outbox(engine: ProcrastinateEngine, db: Engine,
                                                             two_workspaces: tuple[str, str],
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    first = make_run(db, ws, conn_id, dataset="a")
    make_run(db, ws, conn_id, dataset="b")
    real = engine.enqueue_locked
    seen: list[uuid.UUID] = []

    def flaky(conn: Any, row: Any, **kw: Any) -> int:
        seen.append(row.id)
        if len(seen) == 2:
            raise RuntimeError("connection lost mid-batch")
        return real(conn, row, **kw)

    monkeypatch.setattr(engine, "enqueue_locked", flaky)
    with pytest.raises(RuntimeError):
        Dispatcher(engine).dispatch()
    assert jobs(db) == []  # the job deferred for the first row rolled back with its stamp
    assert run_row(db, first)["enqueued_at"] is None
    monkeypatch.setattr(engine, "enqueue_locked", real)
    assert Dispatcher(engine).dispatch().total == 2


# -- fairness: queues, stream locks, priority ---------------------------------------------------------


def test_incremental_jumps_queued_backfill_chunks_on_its_stream(engine: ProcrastinateEngine, db: Engine,
                                                               two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    chunks = [make_run(db, ws, conn_id, kind="backfill", hour=-h) for h in range(1, 6)]
    Dispatcher(engine).dispatch()
    incremental = make_run(db, ws, conn_id)
    Dispatcher(engine).dispatch()
    first = fetch(db, [SYNC_QUEUE, BACKFILL_QUEUE])
    assert first is not None and first["args"] == {"run_id": str(incremental)}
    # While it runs nothing else on that stream starts, backfill included.
    assert fetch(db, [SYNC_QUEUE, BACKFILL_QUEUE]) is None
    finish(db, first["id"])
    nxt = fetch(db, [BACKFILL_QUEUE])
    assert nxt is not None and nxt["args"] == {"run_id": str(chunks[0])}


def test_a_running_backfill_holds_its_stream_but_not_others(engine: ProcrastinateEngine, db: Engine,
                                                            two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    busy, other = make_connection(db, ws), make_connection(db, ws)
    make_run(db, ws, busy, kind="backfill")
    Dispatcher(engine).dispatch()
    running = fetch(db, [BACKFILL_QUEUE])
    assert running is not None
    blocked = make_run(db, ws, busy)
    free = make_run(db, ws, other)
    Dispatcher(engine).dispatch()
    picked = fetch(db, [SYNC_QUEUE])
    assert picked is not None and picked["args"] == {"run_id": str(free)}
    assert fetch(db, [SYNC_QUEUE]) is None  # same stream as the running backfill: waits
    finish(db, running["id"])
    picked = fetch(db, [SYNC_QUEUE])
    assert picked is not None and picked["args"] == {"run_id": str(blocked)}


# -- workers -----------------------------------------------------------------------------------------


def test_worker_calls_the_executor_with_each_run_id(engine: ProcrastinateEngine, db: Engine,
                                                    recorder: Recorder,
                                                    two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    runs = {make_run(db, ws, conn_id, dataset="a"), make_run(db, ws, conn_id, dataset="b", kind="backfill")}
    Dispatcher(engine).dispatch()
    engine.run_worker(queues=[SYNC_QUEUE, BACKFILL_QUEUE], until_idle=True)
    assert set(recorder.calls) == runs
    assert {j["status"] for j in jobs(db)} == {"succeeded"}


def test_waiting_runs_go_back_in_the_queue_when_due(engine: ProcrastinateEngine, db: Engine,
                                                    two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    soon = make_run(db, ws, conn_id, dataset="soon")
    later = make_run(db, ws, conn_id, dataset="later")

    def runner_waits(run_id: uuid.UUID) -> None:  # what ledger.wait does after a 429
        delay = timedelta(seconds=-1) if run_id == soon else timedelta(hours=1)
        with db.begin() as conn:
            conn.execute(text("update sync_runs set status = 'waiting', next_attempt_at = now() + :delay"
                              " where id = :id"), {"id": run_id, "delay": delay})

    engine.set_executor(runner_waits)
    dispatcher = Dispatcher(engine)
    dispatcher.dispatch()
    # Still running: the job that just set `waiting` hasn't finished, so nothing is re-queued yet.
    with db.begin() as conn:
        conn.execute(text("update sync_runs set status = 'waiting', next_attempt_at = now() where id = :id"),
                     {"id": soon})
        conn.execute(text("update procrastinate_jobs set status = 'doing'"))
    assert dispatcher.dispatch().total == 0
    with db.begin() as conn:
        conn.execute(text("update procrastinate_jobs set status = 'todo'"))
        conn.execute(text("update sync_runs set status = 'queued' where id = :id"), {"id": soon})
    engine.run_worker(queues=[SYNC_QUEUE], until_idle=True)
    result = dispatcher.dispatch()
    assert result.new == [] and result.resumed == [soon]  # `later` isn't due for an hour
    assert dispatcher.dispatch().total == 0  # its new job is todo: not queued twice
    assert [j["args"]["run_id"] for j in jobs(db)].count(str(soon)) == 2
    assert run_row(db, soon)["queue_job_id"] == jobs(db)[-1]["id"]
    assert run_row(db, later)["status"] == "waiting"


def test_a_stalled_job_is_retried_and_runs(engine: ProcrastinateEngine, db: Engine, recorder: Recorder,
                                           two_workspaces: tuple[str, str]) -> None:
    ws, _ = two_workspaces
    conn_id = make_connection(db, ws)
    run_id = make_run(db, ws, conn_id)
    Dispatcher(engine).dispatch()
    # A worker took the job and died: its heartbeat stopped five minutes ago.
    with db.begin() as conn:
        dead = conn.execute(text("insert into procrastinate_workers (last_heartbeat)"
                                 " values (now() - interval '5 minutes') returning id")).scalar_one()
        conn.execute(text("update procrastinate_jobs set status = 'doing', worker_id = :w"), {"w": dead})
    # A live worker's job is left alone.
    other = make_run(db, ws, conn_id, dataset="live")
    Dispatcher(engine).dispatch()
    with db.begin() as conn:
        live = conn.execute(text("insert into procrastinate_workers (last_heartbeat) values (now())"
                                 " returning id")).scalar_one()
        conn.execute(text("update procrastinate_jobs set status = 'doing', worker_id = :w"
                          " where args->>'run_id' = :r"), {"w": live, "r": str(other)})
    assert fetch(db, [SYNC_QUEUE]) is None  # stuck: nothing else can run on that stream either

    async def recover() -> list[int]:
        async with engine.app.open_async():
            return await engine.retry_stalled_jobs_async()

    retried = asyncio.run(recover())
    assert [j["status"] for j in jobs(db) if j["id"] in retried] == ["todo"]
    assert len(retried) == 1
    engine.run_worker(queues=[SYNC_QUEUE], until_idle=True)
    assert recorder.calls == [run_id]


def test_stalled_job_recovery_is_a_periodic_task(engine: ProcrastinateEngine) -> None:
    periodic = {task.task.name: task for task in engine.app.periodic_registry.periodic_tasks.values()}
    assert periodic[RETRY_STALLED_TASK].cron == "* * * * *"
    assert engine.app.tasks[RETRY_STALLED_TASK].queue == "maintenance"
