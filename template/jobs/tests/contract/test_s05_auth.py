"""Scenario 5: revoked token; refresh race.

Must observe: connection becomes reconnect_needed; one rotation wins; nothing overwritten."""

from datetime import timedelta

from jobs.sync.contract import AuthRevoked, ConnectionState, Credential, RunStatus, TokenRefresher
from jobs.sync.runner import Outcome
from jobs.sync.testing.world import ACCOUNTS

from .harness import Harness


def test_revoked_token_marks_reconnect_needed_without_blind_retries(implementations: Harness) -> None:
    h = implementations
    h.world.revoke_all(h.a.connection_id)
    run_a = h.submit(h.spec(h.a))
    run_b = h.submit(h.spec(h.b))
    h.drain()

    row = h.run_row(run_a)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "auth_revoked"
    assert h.connections.get(h.a.connection_id) is ConnectionState.RECONNECT_NEEDED
    assert h.connections.get(h.b.connection_id) is ConnectionState.HEALTHY
    assert h.run(run_b).status is RunStatus.SUCCEEDED  # the other workspace is untouched
    assert [c for c in h.feed.calls] == [("fetch_page", None), ("fetch_page", None)]
    events = [e for e in h.audit.events if e.action == "connection.auth_revoked"]
    assert len(events) == 1
    assert events[0].workspace_id == h.a.workspace_id and events[0].actor_type == "system"

    # A new run on the revoked connection never reaches the provider.
    calls = h.feed.call_count
    later = h.submit(h.spec(h.a, dataset=ACCOUNTS))
    h.drain()
    assert h.run_row(later).error_code == "connection_unavailable"
    assert h.feed.call_count == calls


def test_refresh_race_one_rotation_wins(implementations: Harness) -> None:
    h = implementations
    expiring = h.clock.now() + timedelta(seconds=10)
    h.put_credential(h.a, "tok-a-0", expires_at=expiring)
    run_events, _ = h.ledger.create_run(h.spec(h.a))
    run_accounts, _ = h.ledger.create_run(h.spec(h.a, dataset=ACCOUNTS))
    original = h.credentials.refresh
    inner: dict[str, Outcome] = {}
    refresh_calls: list[int] = []

    def racing_refresh(cred: Credential, refresher: TokenRefresher) -> Credential:
        refresh_calls.append(cred.version)
        if not inner:
            # Worker 1 read version 1 and wants to refresh; worker 2 gets the lock first and refreshes.
            inner["second"] = h.once(run_accounts, owner="worker-2")
        return original(cred, refresher)

    h.credentials.refresh = racing_refresh  # type: ignore[method-assign]
    first = h.once(run_events, owner="worker-1")

    assert inner["second"] is Outcome.SUCCEEDED
    assert first is Outcome.SUCCEEDED
    assert h.feed.refreshes == 1  # the loser never called the provider
    stored = h.credentials.get(h.a.connection_id)
    assert stored.version == 2  # exactly one rotation was saved
    assert refresh_calls == [1, 1]  # both workers asked with version 1; only one refresh happened
    assert stored.access_token == "tok-" + str(h.a.connection_id)[:8] + "-r1"  # worker 2's token kept
    assert h.connections.get(h.a.connection_id) is ConnectionState.HEALTHY


def test_revoked_refresh_marks_reconnect_needed(implementations: Harness) -> None:
    h = implementations
    h.put_credential(h.a, "tok-a-0", expires_at=h.clock.now())

    def revoked(cred: Credential) -> tuple[str, object]:
        raise AuthRevoked("refresh grant revoked tok-a-0")

    h.feed.refresh_token = revoked  # type: ignore[method-assign,assignment]
    run_id = h.submit(h.spec(h.a))
    h.drain()

    assert h.run_row(run_id).error_code == "auth_revoked"
    assert h.credential_version() == 1  # nothing saved
    assert h.connections.get(h.a.connection_id) is ConnectionState.RECONNECT_NEEDED
    assert h.feed.call_count == 0
