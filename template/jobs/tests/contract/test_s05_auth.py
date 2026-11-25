"""Scenario 5: revoked token; refresh race.

Must observe: connection becomes reconnect_needed; one rotation wins; nothing overwritten."""

from datetime import timedelta

from jobs.sync.contract import ConnectionState, Credential, RunStatus
from jobs.sync.runner import Outcome
from jobs.sync.testing.world import ACCOUNTS

from .harness import A, B, Harness


def test_revoked_token_marks_reconnect_needed_without_blind_retries(implementations: Harness) -> None:
    h = implementations
    h.world.revoke_all(A.connection_id)
    run_a = h.submit(h.spec(A))
    run_b = h.submit(h.spec(B))
    h.drain()

    row = h.run_row(run_a)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "auth_revoked"
    assert h.connections.get(A.connection_id) is ConnectionState.RECONNECT_NEEDED
    assert h.connections.get(B.connection_id) is ConnectionState.HEALTHY
    assert h.run(run_b).status is RunStatus.SUCCEEDED  # the other workspace is untouched
    assert [c for c in h.feed.calls] == [("fetch_page", None), ("fetch_page", None)]
    events = [e for e in h.audit.events if e.action == "connection.reconnect_needed"]
    assert len(events) == 1
    assert events[0].workspace_id == A.workspace_id and events[0].actor_type == "system"

    # A new run on the revoked connection never reaches the provider.
    calls = h.feed.call_count
    later = h.submit(h.spec(A, dataset=ACCOUNTS))
    h.drain()
    assert h.run_row(later).error_code == "connection_unavailable"
    assert h.feed.call_count == calls


def test_refresh_race_one_rotation_wins(implementations: Harness) -> None:
    h = implementations
    expiring = h.clock.now() + timedelta(seconds=10)
    h.credentials.put(A.connection_id, "tok-a-0", expires_at=expiring)
    run_events, _ = h.ledger.create_run(h.spec(A))
    run_accounts, _ = h.ledger.create_run(h.spec(A, dataset=ACCOUNTS))
    original = h.feed.refresh_token
    inner: dict[str, Outcome] = {}

    def racing_refresh(cred: Credential) -> tuple[str, object]:
        if not inner:
            # Worker 1 has read version 1 and is refreshing; worker 2 refreshes and rotates first.
            inner["second"] = h.once(run_accounts, owner="worker-2")
        return original(cred)

    h.feed.refresh_token = racing_refresh  # type: ignore[method-assign,assignment]
    first = h.once(run_events, owner="worker-1")

    assert inner["second"] is Outcome.SUCCEEDED
    assert first is Outcome.SUCCEEDED
    stored = h.credentials.get(A.connection_id)
    assert stored.version == 2  # exactly one rotation was saved
    assert h.credentials.rotations == 1
    assert h.credentials.lost_races == 1
    assert stored.access_token == "tok-" + str(A.connection_id)[:8] + "-r1"  # worker 2's token kept
    assert h.connections.get(A.connection_id) is ConnectionState.HEALTHY
