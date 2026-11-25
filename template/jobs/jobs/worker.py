"""The jobs process: `python -m jobs.worker [--role all|worker|clock]`.

- worker: Procrastinate worker loops, one per queue so each has its own concurrency (`sync`,
  `backfill`, `maintenance`). The maintenance loop runs the periodic tasks: stalled-job recovery, old
  job cleanup, and the jobs in schedules.yaml (billing_reconcile, sample_fetch).
- clock: the dispatcher (every DISPATCH_INTERVAL_S) and the sync scheduler (every SCHEDULE_INTERVAL_S).
  Both are safe to run in several processes at once.
- all (the default, what Compose runs): both, in one process.

Runs are executed by `run_executor(run_id)`. The real runner (jobs/sync/runner.py) plugs in through
SYNC_EXECUTOR, "module:attribute" naming a zero-argument factory that returns a callable
`(run_id: uuid.UUID) -> None`; the default is `jobs.sync.runner:build_executor`. Tests and other
entrypoints call `install_executor` instead.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import importlib
import logging
import os
import signal
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from jobs.runner import run as run_handler
from jobs.sync.dispatcher import Dispatcher
from jobs.sync.engine import (
    BACKFILL_QUEUE,
    MAINTENANCE_QUEUE,
    SYNC_QUEUE,
    Executor,
    ExecutorMissing,
    ProcrastinateEngine,
)
from jobs.sync.scheduler import Scheduler

SCHEDULES = Path(__file__).resolve().parents[1] / "schedules.yaml"
DEFAULT_EXECUTOR = "jobs.sync.runner:build_executor"
log = logging.getLogger("jobs.worker")


# -- the run executor hook ---------------------------------------------------------------------------

_executor: Executor | None = None


def install_executor(executor: Executor | None) -> None:
    global _executor
    _executor = executor


def load_executor(spec: str | None = None) -> Executor | None:
    """The executor named by SYNC_EXECUTOR (or the default). None if that module isn't there yet."""
    target = spec or os.environ.get("SYNC_EXECUTOR") or DEFAULT_EXECUTOR
    module_name, _, attribute = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if spec is None and target == DEFAULT_EXECUTOR and exc.name == module_name:
            return None
        raise
    factory: Callable[[], Executor] | None = getattr(module, attribute or "build_executor", None)
    if factory is None:
        if spec is None and target == DEFAULT_EXECUTOR:
            return None  # the runner exists but its factory isn't wired yet
        raise AttributeError(f"{target} not found")
    return factory()


def run_executor(run_id: uuid.UUID) -> None:
    """What the `sync.run` queue job calls. The queue job carries the run id and nothing else."""
    if _executor is None:
        raise ExecutorMissing(f"no run executor installed; run {run_id} stays queued in the ledger")
    _executor(run_id)


# -- periodic jobs from schedules.yaml ---------------------------------------------------------------


@dataclass(frozen=True)
class PeriodicJob:
    name: str  # module under jobs/handlers
    cron: str  # UTC


def load_schedules(path: Path = SCHEDULES) -> list[PeriodicJob]:
    raw = yaml.safe_load(path.read_text()) or {}
    return [PeriodicJob(str(s["job"]), str(s["cron"])) for s in raw.get("schedules", [])]


def register_periodic(engine: ProcrastinateEngine, jobs: list[PeriodicJob]) -> None:
    """Each schedules.yaml job becomes a Procrastinate periodic task on the maintenance queue. Every
    worker runs the periodic deferrer; Procrastinate defers each (task, timestamp) once in all, and the
    queueing lock stops a slow run from piling up a backlog of the same job."""
    for job in jobs:

        def task(timestamp: int, _name: str = job.name) -> None:
            log.info("%s %s", _name, run_handler(_name, {}))

        engine.app.periodic(cron=job.cron, periodic_id=job.name)(
            engine.app.task(name=f"periodic.{job.name}", queue=MAINTENANCE_QUEUE,
                            queueing_lock=f"periodic.{job.name}")(task))

    async def remove_old_jobs(timestamp: int) -> None:
        # Finished queue jobs are kept three days for debugging; failed ones too, a week.
        await engine.app.job_manager.delete_old_jobs(nb_hours=72)
        await engine.app.job_manager.delete_old_jobs(nb_hours=168, include_failed=True,
                                                     include_cancelled=True, include_aborted=True)

    engine.app.periodic(cron="17 3 * * *", periodic_id="cleanup")(
        engine.app.task(name="periodic.remove_old_jobs", queue=MAINTENANCE_QUEUE,
                        queueing_lock="periodic.remove_old_jobs")(remove_old_jobs))


def build(database_url: str | None = None, *, executor: Executor | None = None,
          schedules: list[PeriodicJob] | None = None) -> ProcrastinateEngine:
    engine = ProcrastinateEngine(database_url or os.environ["DATABASE_URL"], executor=run_executor)
    if executor is not None:
        install_executor(executor)
    register_periodic(engine, load_schedules() if schedules is None else schedules)
    return engine


# -- the process -------------------------------------------------------------------------------------


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


def clock(engine: ProcrastinateEngine, stop: threading.Event) -> None:
    """Dispatcher and scheduler loops. A failing pass is logged and retried on the next interval."""
    dispatcher = Dispatcher(engine)
    scheduler = Scheduler(engine.db)
    dispatch_every = _env_float("DISPATCH_INTERVAL_S", 2.0)
    schedule_every = _env_float("SCHEDULE_INTERVAL_S", 15.0)
    next_schedule = 0.0
    elapsed = 0.0
    while not stop.is_set():
        if elapsed >= next_schedule:
            try:
                scheduler.tick()
            except Exception:
                log.exception("scheduler tick failed")
            next_schedule = elapsed + schedule_every
        try:
            dispatcher.drain()
        except Exception:
            log.exception("dispatch failed")
        stop.wait(dispatch_every)
        elapsed += dispatch_every


async def serve(engine: ProcrastinateEngine, role: str) -> None:
    stop = threading.Event()
    async with engine.app.open_async():
        loops: list[Any] = []
        if role in ("all", "worker"):
            common: dict[str, Any] = {"install_signal_handlers": False, "wait": True}
            loops += [
                engine.app.run_worker_async(name="sync", queues=[SYNC_QUEUE],
                                            concurrency=_env_int("SYNC_CONCURRENCY", 4), **common),
                engine.app.run_worker_async(name="backfill", queues=[BACKFILL_QUEUE],
                                            concurrency=_env_int("BACKFILL_CONCURRENCY", 1), **common),
                engine.app.run_worker_async(name="maintenance", queues=[MAINTENANCE_QUEUE],
                                            concurrency=1, **common),
            ]
        if role in ("all", "clock"):
            loops.append(asyncio.to_thread(clock, engine, stop))
        main = asyncio.ensure_future(asyncio.gather(*loops))

        def shutdown() -> None:
            log.info("stopping")
            stop.set()  # the clock thread ends at its next wait
            main.cancel()  # Procrastinate workers finish their running jobs, then return

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, shutdown)
        with contextlib.suppress(asyncio.CancelledError):
            await main


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="jobs.worker")
    parser.add_argument("--role", choices=("all", "worker", "clock"), default="all")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    executor = load_executor()
    if executor is None:
        log.warning("no run executor (%s not found): sync runs will fail until one is installed",
                    DEFAULT_EXECUTOR)
    engine = build(executor=executor)
    asyncio.run(serve(engine, args.role))


if __name__ == "__main__":
    main()
