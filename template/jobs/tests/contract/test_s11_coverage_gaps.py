"""Scenario 11: a hole in coverage, then later windows succeed before the hole is filled.

A scheduled run fails (or the scheduler was down past its catch-up window) and the next scheduled
windows succeed. Coverage must stop at the hole and not claim it, but once the hole is filled, coverage
must take in the later windows that already succeeded. Otherwise every later window is "past the gap"
and coverage never moves again.

Must observe: coverage never spans an unpublished window; filling the hole joins everything published
after it; the next window after that extends coverage as usual."""

from datetime import timedelta

from jobs.sync.contract import RunStatus, Window

from .harness import START, Harness

H = timedelta(hours=6)


def _publish(h: Harness, start: int, end: int) -> None:
    run_id = h.submit(h.spec(window=Window(START + start * H, START + end * H)))
    h.drain()
    assert h.run(run_id).status is RunStatus.SUCCEEDED


def test_coverage_stops_at_a_hole(implementations: Harness) -> None:
    h = implementations
    _publish(h, 0, 1)
    _publish(h, 2, 3)  # [1, 2) is the hole
    _publish(h, 3, 4)
    assert h.coverage() == (START, START + 1 * H)


def test_filling_the_hole_joins_the_windows_published_after_it(implementations: Harness) -> None:
    h = implementations
    _publish(h, 0, 1)
    _publish(h, 2, 3)
    _publish(h, 3, 4)
    _publish(h, 1, 2)  # the retry, backfill or refresh that fills the hole
    assert h.coverage() == (START, START + 4 * H)

    _publish(h, 4, 5)  # the next scheduled window extends it as usual
    assert h.coverage() == (START, START + 5 * H)


def test_a_window_reaching_back_over_the_hole_joins_everything(implementations: Harness) -> None:
    h = implementations
    _publish(h, 0, 1)
    _publish(h, 3, 4)
    _publish(h, 5, 6)  # [4, 5) is a second hole
    _publish(h, 1, 3)  # fills only the first hole
    assert h.coverage() == (START, START + 4 * H)


def test_failed_windows_do_not_count(implementations: Harness) -> None:
    h = implementations
    _publish(h, 0, 1)
    _publish(h, 2, 3)
    h.world.revoke_all(h.a.connection_id)  # the hole's run fails for good
    run_id = h.submit(h.spec(window=Window(START + 1 * H, START + 2 * H)))
    h.drain()
    assert h.run(run_id).status is not RunStatus.SUCCEEDED
    assert h.coverage() == (START, START + 1 * H)
