"""Scenario 10: pause, resume, replay.

Must observe: bounded behavior, connector version traced, audit event written."""

import itertools

from jobs.sync.contract import ConnectionState, RunStatus, Window
from jobs.sync.runner import Outcome
from jobs.sync.testing import Fault, FaultPlan, FaultRule

from . import thresholds as T
from .harness import DAY, START, Harness


def test_a_paused_connection_waits_cheaply_then_resumes(implementations: Harness) -> None:
    h = implementations
    h.connections.set(h.a.connection_id, ConnectionState.PAUSED, actor="user-1")
    run_id = h.submit(h.spec())
    h.engine.run_steps(4)

    assert h.provider_calls == T.MAX_PROVIDER_CALLS_WHILE_PAUSED
    assert all(e.outcome is Outcome.WAITING for e in h.engine.history)
    hist = h.engine.history
    assert all((b.at - a.at).total_seconds() >= T.PAUSE_RECHECK_S for a, b in itertools.pairwise(hist))
    assert h.run(run_id).status is RunStatus.WAITING

    h.connections.set(h.a.connection_id, ConnectionState.HEALTHY, actor="user-1")
    h.drain()
    assert h.run(run_id).status is RunStatus.SUCCEEDED
    actions = [(e.actor_type, e.action) for e in h.audit.events]
    assert ("user", "connection.paused") in actions and ("user", "connection.healthy") in actions


def test_pausing_mid_run_finishes_the_current_page_only(implementations: Harness) -> None:
    h = implementations
    run_id = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    latency = h.world.on_call

    def pause_during_first_fetch() -> None:
        latency()
        if h.feed.call_count == 1:
            h.connections.set(h.a.connection_id, ConnectionState.PAUSED, actor="user-1")

    h.world.on_call = pause_during_first_fetch
    h.engine.run_steps(1)
    assert h.feed.call_count == 1
    assert h.run_row(run_id).wait_reason == "connection_paused"
    assert all(r.processed for r in h.ledger.raw_objects(run_id))  # the page in hand was published

    h.connections.set(h.a.connection_id, ConnectionState.HEALTHY, actor="user-1")
    h.drain()
    assert h.run(run_id).status is RunStatus.SUCCEEDED
    assert len(h.records()) == 9


def test_replay_republishes_stored_raw_with_the_new_connector(implementations: Harness) -> None:
    h = implementations
    window = Window(START, START + 3 * DAY)
    source = h.submit(h.spec(window=window))
    h.drain()
    fetches = h.feed.call_count

    h.feed.version = "2"
    replay = h.ledger.create_replay(source, connector_version="2")
    h.engine.enqueue(replay)
    h.drain()

    run = h.run(replay)
    assert run.status is RunStatus.SUCCEEDED
    assert run.spec.connector_version == "2"
    assert run.checkpoint["connector_version"] == "2"
    assert h.feed.call_count == fetches  # replay never calls the provider
    [event] = [e for e in h.audit.events if e.action == "run.replay"]
    assert event.actor_type == "system"
    assert event.detail["connector_version"] == "2"
    assert event.detail["source_connector_version"] == "1"
    assert event.detail["coverage_advanced"] is True
    assert len(h.records()) == 9
    assert h.coverage() == (window.start, window.end)

    again = h.ledger.create_replay(source, connector_version="2")
    h.engine.enqueue(again)
    h.drain()
    assert h.run(again).status is RunStatus.SUCCEEDED
    assert len(h.records()) == 9  # idempotent


def test_replay_after_a_schema_fix_publishes_but_does_not_claim_coverage(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.SCHEMA_CHANGE, at_call=2)])
    source = h.submit(h.spec(window=Window(START, START + 3 * DAY)))
    h.drain()
    assert len(h.records()) == 4

    h.feed.version = "2"  # the fixed connector understands the new schema
    replay = h.ledger.create_replay(source, connector_version="2")
    h.engine.enqueue(replay)
    h.drain()

    row = h.run_row(replay)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "replay_source_incomplete"
    assert len(h.records()) == 8  # the kept page is now published
    assert all(r.processed for r in h.ledger.raw_objects(source))
    assert h.coverage() == (None, None)  # page 3 was never fetched
    [event] = [e for e in h.audit.events if e.action == "run.replay"]
    assert event.detail["coverage_advanced"] is False
