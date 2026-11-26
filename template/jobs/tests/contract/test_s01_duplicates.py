"""Scenario 1: duplicate timer or webhook; restart after records are written.

Must observe: one logical record per key and version; duplicate attempts visible on the run."""

from dataclasses import replace

import pytest

from jobs.sync.contract import RunStatus, Trigger, Window
from jobs.sync.runner import Outcome
from jobs.sync.testing import Fault, FaultPlan, FaultRule

from . import thresholds as T
from .harness import DAY, START, Harness, WorkerKilled


def test_duplicate_timer_and_webhook_make_one_run(implementations: Harness) -> None:
    h = implementations
    spec = h.spec()
    first = h.submit(spec)
    second = h.submit(replace(spec, trigger=Trigger.WEBHOOK))
    assert first == second  # one run per unit of work

    h.drain()

    outcomes = [e.outcome for e in h.engine.history]
    assert outcomes.count(Outcome.SUCCEEDED) == 1
    assert outcomes.count(Outcome.NOOP) == 1  # the duplicate delivery did nothing
    assert h.feed.call_count == 1
    assert len(h.records()) == 3


def test_duplicate_delivery_from_the_provider_keeps_one_record_per_key(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.DUPLICATE, at_call=2)])
    run_id = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    h.drain()

    assert h.run(run_id).status is RunStatus.SUCCEEDED
    records = h.records()
    assert len(records) == 9  # 3 days x 3, though page 2 repeated page 1
    assert h.run_row(run_id).records_accepted > 9  # the repeats were delivered and absorbed


@pytest.mark.parametrize("die_after", ["publish", "checkpoint", "save_raw"])
def test_restart_after_records_are_written(implementations: Harness, die_after: str) -> None:
    h = implementations
    run_id = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    h.kill.arm(die_after)
    with pytest.raises(WorkerKilled):
        h.drain()
    assert h.recover_stalled() == [run_id]
    h.drain()

    run = h.run(run_id)
    assert run.status is RunStatus.SUCCEEDED
    assert run.attempt == 2  # the crashed attempt is visible
    records = h.records()
    assert len(records) == 9
    assert len({(k, r.version) for k, r in records.items()}) == 9
    assert h.run_row(run_id).records_accepted == 9  # no page published twice
    raws = h.ledger.raw_objects(run_id)
    assert sorted(r.page_seq for r in raws) == list(range(len(raws)))  # no page recorded twice
    assert len(raws) == 3
    assert h.feed.call_count <= 3 + 1  # at most the page in flight is fetched again
    assert h.provider_calls <= T.MAX_PROVIDER_CALLS_PER_SCENARIO
