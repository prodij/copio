"""Scenario 3: two workers claim one stream.

Must observe: only the current fence publishes; the stale worker gets StaleLease and writes nothing."""

from jobs.sync.contract import RunStatus, Window
from jobs.sync.runner import Outcome

from . import thresholds as T
from .harness import DAY, START, Harness


def test_the_stale_worker_writes_nothing(implementations: Harness) -> None:
    h = implementations
    window = Window(START, START + 3 * DAY)
    run_id, _ = h.ledger.create_run(h.spec(window=window))
    state: dict[str, object] = {"calls": 0, "writes_after_takeover": None, "b": None}
    latency = h.world.on_call

    def on_call() -> None:
        latency()
        state["calls"] = int(state["calls"]) + 1  # type: ignore[call-overload]
        if state["calls"] == 2 and state["b"] is None:
            # Worker A stalls inside its second fetch long enough for its lease to expire...
            h.clock.advance(T.LEASE_S + 1)
            # ...and worker B claims the stream and finishes the run.
            state["b"] = h.once(run_id, owner="worker-B")
            state["writes_after_takeover"] = h.kill.writes

    h.world.on_call = on_call
    outcome_a = h.once(run_id, owner="worker-A")

    assert state["b"] is Outcome.SUCCEEDED
    assert outcome_a is Outcome.STALE
    assert h.kill.writes == state["writes_after_takeover"]  # A wrote nothing after the takeover
    run = h.run(run_id)
    assert run.status is RunStatus.SUCCEEDED
    assert run.attempt == 2
    raws = h.ledger.raw_objects(run_id)
    assert len(raws) == 3
    assert sum("/f1-" in r.storage_key for r in raws) == 1  # only the page A saved while it held the lease
    assert len(h.records()) == 9


def test_a_live_lease_blocks_a_second_claim(implementations: Harness) -> None:
    h = implementations
    run_id, _ = h.ledger.create_run(h.spec())
    lease = h.ledger.claim(run_id, "worker-A", T.LEASE_S)
    assert lease is not None
    assert h.once(run_id, owner="worker-B") is Outcome.BUSY
    assert h.feed.call_count == 0
