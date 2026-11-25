"""Scenario 6: large backfill next to a small incremental.

Must observe: the incremental finishes within the threshold's budget."""

from jobs.sync.contract import RunKind, RunStatus, Window
from jobs.sync.runner import Outcome

from . import thresholds as T
from .harness import DAY, START, Harness


def test_incremental_finishes_while_a_backfill_runs(implementations: Harness) -> None:
    h = implementations
    backfill_window = Window(START - 30 * DAY, START)
    backfill = h.submit(h.spec(kind=RunKind.BACKFILL, window=backfill_window))
    h.engine.run_steps(1)  # the backfill is under way and has yielded once
    assert h.run(backfill).status is RunStatus.WAITING

    submitted_at = h.clock.now()
    incremental = h.submit(h.spec(window=Window(START, START + DAY)))
    h.drain()

    done = [e for e in h.engine.history if e.run_id == incremental and e.outcome is Outcome.SUCCEEDED]
    assert len(done) == 1
    assert (done[0].finished_at - submitted_at).total_seconds() <= T.MAX_INCREMENTAL_WALL_S_DURING_BACKFILL
    assert h.run(backfill).status is RunStatus.SUCCEEDED
    assert "backfill_yield" in h.run_row(backfill).waits
    assert h.coverage() == (backfill_window.start, START + DAY)  # contiguous, both pieces
    assert len(h.records()) == 31 * 3
    assert h.provider_calls <= T.MAX_PROVIDER_CALLS_PER_SCENARIO
