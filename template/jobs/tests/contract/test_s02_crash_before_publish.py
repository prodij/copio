"""Scenario 2: worker killed after save_raw, before publish.

Must observe: recovery publishes or fails boundedly; coverage never advances past unpublished raw."""

import pytest

from jobs.sync.contract import RunStatus, Window

from . import thresholds as T
from .harness import DAY, START, Harness, WorkerKilled


def test_recovery_publishes_the_saved_raw(implementations: Harness) -> None:
    h = implementations
    window = Window(START, START + 3 * DAY)
    run_id = h.submit(h.spec(window=window))
    h.kill.arm("save_raw", on_call=2)
    with pytest.raises(WorkerKilled):
        h.drain()

    backlog = [r for r in h.ledger.raw_objects(run_id) if not r.processed]
    assert len(backlog) == 1
    assert h.coverage() == (None, None)  # never past unpublished raw

    h.recover_stalled()
    fetches_before = h.feed.call_count
    h.drain()

    assert h.run(run_id).status is RunStatus.SUCCEEDED
    assert all(r.processed for r in h.ledger.raw_objects(run_id))
    assert h.coverage() == (window.start, window.end)
    assert len(h.records()) == 9
    assert h.feed.call_count - fetches_before == 1  # the saved page was not fetched again


def test_a_crash_loop_fails_boundedly(implementations: Harness) -> None:
    h = implementations
    run_id = h.submit(h.spec())

    def die() -> None:  # the worker dies inside every fetch, before it can save anything
        raise WorkerKilled("fetch")

    h.world.on_call = die
    deaths = 0
    for _ in range(T.MAX_CLAIMS_PER_RUN + 5):
        try:
            h.drain()
        except WorkerKilled:
            deaths += 1
            h.recover_stalled()
            continue
        break

    run = h.run(run_id)
    assert run.status is RunStatus.FAILED
    assert h.run_row(run_id).error_code == "attempts_exhausted"
    assert deaths == T.MAX_CLAIMS_PER_RUN
    assert h.coverage() == (None, None)
    assert h.feed.call_count == T.MAX_CLAIMS_PER_RUN  # one fetch per claim, no more
