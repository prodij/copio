"""Scenario 9: schema change, missing page, partial snapshot.

Must observe: coverage not advanced; no false completion; no mass deletion."""

from jobs.sync.contract import RunStatus, Window
from jobs.sync.testing import Fault, FaultPlan, FaultRule
from jobs.sync.testing.world import ACCOUNTS

from . import thresholds as T
from .harness import DAY, START, Harness


def test_schema_change_keeps_the_raw_and_does_not_complete(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.SCHEMA_CHANGE, at_call=2)])
    run_id = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    h.drain()

    row = h.run_row(run_id)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "permanent"
    assert h.coverage() == (None, None)
    unpublished = [r for r in h.ledger.raw_objects(run_id) if not r.processed]
    assert len(unpublished) == 1  # the unparseable body is kept for a replay
    assert len(h.records()) == 4  # page 1 only
    assert h.feed.call_count == 2  # a permanent error is not retried


def test_missing_page_fails_without_advancing_coverage(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.MISSING_PAGE, at_call=2)])
    run_id = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    h.drain()

    assert h.run_row(run_id).status is RunStatus.FAILED
    assert h.coverage() == (None, None)
    assert h.feed.call_count == 2


def _full_snapshot(h: Harness) -> None:
    run_id = h.submit(h.spec(dataset=ACCOUNTS, window=Window(START, START + DAY)))
    h.drain()
    assert h.run(run_id).status is RunStatus.SUCCEEDED


def test_partial_snapshot_never_deletes_or_completes(implementations: Harness) -> None:
    h = implementations
    _full_snapshot(h)
    assert len(h.records(dataset=ACCOUNTS)) == 6

    h.feed.faults = FaultPlan([FaultRule(Fault.PARTIAL_SNAPSHOT, at_call=h.feed.call_count + 1,
                                         times=1000)])
    run_id = h.submit(h.spec(dataset=ACCOUNTS, window=Window(START + DAY, START + 2 * DAY)))
    h.drain()

    row = h.run_row(run_id)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "partial_snapshot"
    assert row.deleted_inferred <= T.MAX_MASS_DELETION
    assert not any(r.deleted for r in h.records(dataset=ACCOUNTS).values())
    assert h.coverage(dataset=ACCOUNTS) == (START, START + DAY)  # not advanced to day 2


def test_a_transient_partial_snapshot_recovers_without_false_deletions(implementations: Harness) -> None:
    h = implementations
    _full_snapshot(h)
    h.feed.faults = FaultPlan([FaultRule(Fault.PARTIAL_SNAPSHOT, at_call=h.feed.call_count + 1)])
    run_id = h.submit(h.spec(dataset=ACCOUNTS, window=Window(START + DAY, START + 2 * DAY)))
    h.drain()

    assert h.run_row(run_id).status is RunStatus.SUCCEEDED
    assert h.run_row(run_id).deleted_inferred == 0
    assert h.coverage(dataset=ACCOUNTS) == (START, START + 2 * DAY)


def test_only_a_complete_snapshot_infers_a_deletion(implementations: Harness) -> None:
    h = implementations
    _full_snapshot(h)
    h.world.remove(h.a.connection_id, ACCOUNTS, "acct-0005")
    run_id = h.submit(h.spec(dataset=ACCOUNTS, window=Window(START + DAY, START + 2 * DAY)))
    h.drain()

    assert h.run_row(run_id).deleted_inferred == 1
    assert h.records(dataset=ACCOUNTS)["acct-0005"].deleted
