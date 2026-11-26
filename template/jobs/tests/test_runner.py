"""Focused tests of jobs.sync.runner on the in-memory fakes. The behavior every implementation must
share is in tests/contract/; these pin the runner's own decisions."""

import hashlib
import uuid
from collections.abc import Iterator
from datetime import timedelta

import boto3
import pytest
from contract.harness import DAY, START, A, Harness, memory_harness
from moto import mock_aws

from jobs.sync.contract import ConnectionState, RunKind, RunStatus, Window
from jobs.sync.runner import ExecutorMisconfigured, Outcome, _safe_ref, deps_from_env, execute
from jobs.sync.testing import Fault, FaultPlan, FaultRule


@pytest.fixture
def h() -> Iterator[Harness]:
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="raw")
        yield memory_harness(client, "raw")


def test_heartbeats_keep_the_lease_on_long_work(h: Harness) -> None:
    h.world.on_call = lambda: h.clock.advance(25)  # each page takes 25s of a 60s lease
    run_id = h.submit(h.spec(window=Window(START, START + 6 * DAY)))
    started = h.clock.now()
    assert h.once(run_id) is Outcome.SUCCEEDED
    assert (h.clock.now() - started).total_seconds() > 2 * 60  # far longer than one lease
    assert h.run(run_id).checkpoint["heartbeats"] >= 2
    assert len(h.records()) == 18


def test_raw_is_stored_under_a_fenced_key_with_a_matching_checksum(h: Harness) -> None:
    run_id = h.submit(h.spec())
    h.drain()
    [raw] = h.ledger.raw_objects(run_id)
    assert f"/{run_id}/f1-p000000.json" in raw.storage_key
    assert raw.storage_key.startswith(f"raw/synthetic-feed/events/{A.workspace_id}/")
    body = h.raw_store.get(raw.storage_key)
    assert hashlib.sha256(body).hexdigest() == raw.sha256 and len(body) == raw.size


def test_terminal_and_unknown_runs_are_noops(h: Harness) -> None:
    run_id = h.submit(h.spec())
    h.drain()
    assert h.once(run_id) is Outcome.NOOP
    assert h.once(uuid.uuid4()) is Outcome.NOOP
    assert h.feed.call_count == 1


def test_disconnected_connection_fails_without_calling_the_provider(h: Harness) -> None:
    h.connections.set(A.connection_id, ConnectionState.DISCONNECTED)
    run_id = h.submit(h.spec())
    h.drain()
    assert h.run_row(run_id).error_code == "connection_unavailable"
    assert h.feed.call_count == 0


def test_a_blocked_budget_waits_without_calling_the_provider(h: Harness) -> None:
    h.feed.faults = FaultPlan([FaultRule(Fault.RATE_LIMITED, at_call=1, retry_after_s=100.0)])
    run_id = h.submit(h.spec())
    assert h.once(run_id) is Outcome.WAITING
    h.clock.advance(10)  # an early redelivery, before blocked_until
    assert h.once(run_id) is Outcome.WAITING
    assert h.feed.call_count == 1
    assert h.run_row(run_id).checkpoint["rate_limit_waits"] == 1  # honoring a block is not a new 429


def test_a_corrupt_raw_object_fails_the_replay(h: Harness) -> None:
    source = h.submit(h.spec())
    h.drain()
    [raw] = h.ledger.raw_objects(source)
    h.raw_store.client.put_object(Bucket="raw", Key=raw.storage_key, Body=b"tampered")
    replay = h.ledger.create_replay(source, connector_version="1")
    assert h.once(replay) is Outcome.FAILED
    assert h.run_row(replay).error_code == "raw_corrupt"


def test_a_report_run_needs_a_report_provider(h: Harness) -> None:
    run_id = h.submit(h.spec(kind=RunKind.REPORT))
    assert execute(run_id, h.deps(providers=lambda spec: h.feed)) is Outcome.FAILED
    assert h.run_row(run_id).error_code == "provider_mismatch"


def test_revoked_auth_during_a_report_marks_reconnect_needed(h: Harness) -> None:
    h.report.faults = FaultPlan([FaultRule(Fault.AUTH_REVOKED, at_call=2)])
    run_id = h.submit(h.spec(kind=RunKind.REPORT))
    h.drain()
    assert h.run_row(run_id).error_code == "auth_revoked"
    assert h.connections.get(A.connection_id) is ConnectionState.RECONNECT_NEEDED
    assert h.report.requests == 1


def test_an_expired_credential_is_refreshed_and_rotated(h: Harness) -> None:
    h.credentials.put(A.connection_id, "tok-a-0", expires_at=h.clock.now() - timedelta(seconds=1))
    run_id = h.submit(h.spec())
    h.drain()
    assert h.run(run_id).status is RunStatus.SUCCEEDED
    assert h.credentials.get(A.connection_id).version == 2
    assert h.feed.refreshes == 1


def test_request_refs_are_reduced_to_an_id_shape() -> None:
    assert _safe_ref("req-12 token=abc {\"x\":1}") == "req-12tokenabcx:1"
    assert _safe_ref("") is None
    assert _safe_ref("x" * 400) == "x" * 255


def test_the_worker_loads_the_executor_lazily(monkeypatch: pytest.MonkeyPatch) -> None:
    from jobs import worker

    monkeypatch.delenv("SYNC_EXECUTOR", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    executor = worker.load_executor()
    assert callable(executor)  # loading builds nothing
    with pytest.raises(ExecutorMisconfigured, match="DATABASE_URL"):
        executor(uuid.uuid4())


def test_a_missing_piece_is_named(monkeypatch: pytest.MonkeyPatch) -> None:
    env = {"DATABASE_URL": "postgresql+psycopg://x@127.0.0.1:1/x", "RAW_BUCKET": "data",
           "SYNC_AUDIT": "jobs.sync.nowhere:PgAuditSink",
           "SYNC_BUDGETS": "jobs.sync.budgets:Budgets",
           "SYNC_CREDENTIALS": "contract.fakes:MemoryCredentialStore"}
    with pytest.raises(ExecutorMisconfigured, match=r"audit \(jobs\.sync\.nowhere:PgAuditSink"):
        deps_from_env(env)
    env["SYNC_AUDIT"] = "contract.fakes:MemoryAudit"
    with pytest.raises(ExecutorMisconfigured, match="SYNC_PROVIDERS"):
        deps_from_env(env)


def test_misconfiguration_never_echoes_secrets() -> None:
    env = {"DATABASE_URL": "postgresql+psycopg://app:s3cret@db/app", "RAW_BUCKET": "data",
           "CONNECTOR_LOCAL_KEK": "c2VjcmV0", "SYNC_LEDGER": "jobs.sync.nowhere:L"}
    with pytest.raises(ExecutorMisconfigured) as info:
        deps_from_env(env)
    assert "s3cret" not in str(info.value) and "c2VjcmV0" not in str(info.value)
