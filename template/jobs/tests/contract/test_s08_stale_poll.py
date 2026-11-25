"""Scenario 8: stale poll after a newer webhook.

Must observe: no stale overwrite."""

from jobs.sync.contract import RunStatus, Trigger, Window
from jobs.sync.testing import Fault, FaultPlan, FaultRule

from .harness import DAY, START, A, Harness


def test_a_stale_poll_never_overwrites_a_newer_webhook(implementations: Harness) -> None:
    h = implementations
    key = f"{START:%Y%m%d}-000"
    newer = h.world.update(A.connection_id, "events", key, rev=2, data={"id": key, "amount": 999})

    # The webhook for the change lands first (a narrow window inside the day).
    webhook = h.submit(h.spec(trigger=Trigger.WEBHOOK,
                              window=Window(START.replace(hour=1), START.replace(hour=2))))
    h.drain()
    assert h.records()[key].version == newer

    # A poll that read the provider before the change publishes afterwards.
    h.feed.faults = FaultPlan([FaultRule(Fault.STALE_READ, at_call=h.feed.call_count + 1)])
    poll = h.submit(h.spec(window=Window(START, START + DAY)))
    h.drain()

    assert h.run(webhook).status is RunStatus.SUCCEEDED
    assert h.run(poll).status is RunStatus.SUCCEEDED
    records = h.records()
    assert records[key].version == newer
    assert records[key].data["amount"] == 999
    assert not any(r.data.get("stale") for r in records.values())
    assert h.run_row(poll).records_stale == 3
