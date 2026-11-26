"""PgLedger on real Postgres: idempotent runs, fenced leases, newer-wins publishing, backlog-gated
completion, contiguous coverage, snapshot-only deletions and verified receipts. Synthetic data only."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError

from jobs.sync.contract import (
    Lease,
    Record,
    RunKind,
    RunSpec,
    RunStatus,
    Stage,
    StaleLease,
    Trigger,
    Window,
)
from jobs.sync.ledger import (
    BacklogPending,
    PgLedger,
    RawObjectMismatch,
    ReceiptMismatch,
    RunNotFound,
    sanitize_detail,
)

T0 = datetime(2026, 11, 1, tzinfo=UTC)
DAY = timedelta(days=1)
SHA_A = "a" * 64
SHA_B = "b" * 64


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 25, 12, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def ledger(clean_tables: Engine, clock: Clock) -> PgLedger:
    return PgLedger(clean_tables, clock=clock)


@pytest.fixture
def conn_id(two_workspaces: tuple[str, str], clean_tables: Engine) -> tuple[uuid.UUID, uuid.UUID]:
    """(workspace_id, connection_id) of one synthetic connection."""
    ws = uuid.UUID(two_workspaces[0])
    cid = uuid.uuid4()
    with clean_tables.begin() as conn:
        conn.execute(text(
            "insert into connections (id, workspace_id, provider, account_ref, display_name)"
            " values (:id, :ws, 'synthetic', 'acct-1', 'Synthetic shop')"), {"id": cid, "ws": ws})
    return ws, cid


def spec(ids: tuple[uuid.UUID, uuid.UUID], *, day: int = 0, days: int = 1, dataset: str = "orders",
         kind: RunKind = RunKind.INCREMENTAL, trigger: Trigger = Trigger.SCHEDULE) -> RunSpec:
    window = Window(T0 + day * DAY, T0 + (day + days) * DAY)
    return RunSpec(ids[0], ids[1], dataset, kind, trigger, window, "synthetic-1")


def rec(key: str, version: str, deleted: bool = False, **data: Any) -> Record:
    return Record(key=key, version=version, data={"key": key, **data}, deleted=deleted)


def row(engine: Engine, sql: str, **params: Any) -> Any:
    with engine.connect() as conn:
        return conn.execute(text(sql), params).one_or_none()


def records(engine: Engine) -> dict[str, tuple[str, bool]]:
    with engine.connect() as conn:
        return {r.record_key: (r.version, r.deleted) for r in conn.execute(text(
            "select record_key, version, deleted from synced_records"))}


def snapshot(engine: Engine) -> list[Any]:
    """Everything a fenced write could touch, to prove a refused write changed nothing."""
    with engine.connect() as conn:
        return [conn.execute(text(f"select * from {t} order by 1, 2")).all()  # noqa: S608
                for t in ("sync_streams", "sync_runs", "raw_objects", "synced_records")]


def run_page(ledger: PgLedger, lease: Lease, seq: int, recs: list[Record], sha: str | None = None) -> None:
    raw = ledger.save_raw(lease, seq, f"raw/{lease.run_id}/{seq}.json", sha or f"{seq:064x}", 10)
    ledger.publish(lease, raw, recs)


def sync(ledger: PgLedger, s: RunSpec, recs: list[Record], *, snapshot_complete: bool = False) -> uuid.UUID:
    run_id, _ = ledger.create_run(s)
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    run_page(ledger, lease, 0, recs)
    ledger.complete(lease, s.window, snapshot_complete=snapshot_complete)
    return run_id


# --- create_run ---------------------------------------------------------------------------------


def test_duplicate_create_returns_the_same_run(ledger: PgLedger, conn_id: Any) -> None:
    first, created = ledger.create_run(spec(conn_id))
    again, created_again = ledger.create_run(spec(conn_id, trigger=Trigger.WEBHOOK))
    assert (created, created_again) == (True, False)
    assert again == first


def test_concurrent_creates_make_one_run(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    results: list[tuple[uuid.UUID, bool]] = []
    barrier = threading.Barrier(8)

    def create() -> None:
        barrier.wait()
        results.append(ledger.create_run(spec(conn_id)))

    threads = [threading.Thread(target=create) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len({r[0] for r in results}) == 1
    assert sum(r[1] for r in results) == 1
    assert row(clean_tables, "select count(*) as n from sync_runs").n == 1


def test_create_refuses_a_connection_from_another_workspace(ledger: PgLedger, conn_id: Any,
                                                           two_workspaces: tuple[str, str]) -> None:
    with pytest.raises(LookupError):
        ledger.create_run(spec((uuid.UUID(two_workspaces[1]), conn_id[1])))


# --- claim, fences and takeover -----------------------------------------------------------------


def test_claim_sets_running_counts_attempts_and_bumps_fence(ledger: PgLedger, conn_id: Any,
                                                           clean_tables: Engine, clock: Clock) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None and lease.fence == 1 and lease.expires_at == clock.now + timedelta(seconds=30)
    r = row(clean_tables, "select status, attempt, started_at from sync_runs where id = :id", id=run_id)
    assert (r.status, r.attempt, r.started_at) == ("running", 1, clock.now)
    with pytest.raises(RunNotFound):
        ledger.claim(uuid.uuid4(), "w1", 30)


def test_claim_refuses_while_another_live_lease_holds_the_stream(ledger: PgLedger, conn_id: Any,
                                                                clock: Clock) -> None:
    first, _ = ledger.create_run(spec(conn_id, day=0))
    second, _ = ledger.create_run(spec(conn_id, day=1))  # same stream, different window
    assert ledger.claim(first, "w1", 30) is not None
    assert ledger.claim(second, "w2", 30) is None
    assert ledger.claim(first, "w2", 30) is None  # not even the same run, while the lease is live
    other, _ = ledger.create_run(spec(conn_id, dataset="refunds"))
    assert ledger.claim(other, "w2", 30) is not None  # other streams are independent
    clock.advance(31)
    lease = ledger.claim(second, "w2", 30)
    assert lease is not None and lease.fence == 2


def test_heartbeat_extends_the_lease(ledger: PgLedger, conn_id: Any, clock: Clock) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    clock.advance(25)
    lease = ledger.heartbeat(lease, 30)
    clock.advance(25)  # 50s after the claim, but only 25s after the heartbeat
    assert ledger.claim(run_id, "w2", 30) is None
    assert lease.expires_at == clock.now + timedelta(seconds=5)


def test_takeover_fences_out_the_stale_holder(ledger: PgLedger, conn_id: Any, clean_tables: Engine,
                                              clock: Clock) -> None:
    s = spec(conn_id)
    run_id, _ = ledger.create_run(s)
    old = ledger.claim(run_id, "slow-worker", 30)
    assert old is not None
    raw = ledger.save_raw(old, 0, "raw/0.json", SHA_A, 10)
    clock.advance(60)  # the slow worker stalls past its lease
    new = ledger.claim(run_id, "fresh-worker", 30)
    assert new is not None and new.fence == old.fence + 1
    attempt = row(clean_tables, "select attempt from sync_runs where id = :id", id=run_id).attempt
    assert attempt == 2

    before = snapshot(clean_tables)
    stale_calls: list[Callable[[], object]] = [
        lambda: ledger.heartbeat(old, 30),
        lambda: ledger.checkpoint(old, Stage.FETCHING, {"cursor": "c9"}),
        lambda: ledger.save_raw(old, 1, "raw/1.json", SHA_B, 10),
        lambda: ledger.publish(old, raw, [rec("k1", "0001")]),
        lambda: ledger.complete(old, s.window, snapshot_complete=True),
        lambda: ledger.wait(old, clock.now + DAY, "rate limited"),
        lambda: ledger.fail(old, "boom", "it broke", None),
    ]
    for call in stale_calls:
        with pytest.raises(StaleLease):
            call()
    assert snapshot(clean_tables) == before  # the stale holder wrote nothing at all

    # The new holder carries on normally.
    assert ledger.publish(new, raw, [rec("k1", "0001")]).accepted == 1
    ledger.complete(new, s.window, snapshot_complete=False)
    with pytest.raises(StaleLease):  # a completed run releases the lease; late writes are refused
        ledger.checkpoint(new, Stage.PUBLISHED, {})


def test_racing_claims_after_expiry_give_one_lease(ledger: PgLedger, conn_id: Any, clock: Clock) -> None:
    runs = [ledger.create_run(spec(conn_id, day=d))[0] for d in range(6)]
    assert ledger.claim(runs[0], "stalled", 30) is not None
    clock.advance(31)
    leases: list[Lease | None] = []
    barrier = threading.Barrier(len(runs))

    def take(run_id: uuid.UUID) -> None:
        barrier.wait()
        leases.append(ledger.claim(run_id, f"w-{run_id}", 30))

    threads = [threading.Thread(target=take, args=(r,)) for r in runs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    won = [lease for lease in leases if lease is not None]
    assert len(won) == 1 and won[0].fence == 2


def test_claim_refuses_finished_runs_but_never_caps_attempts(ledger: PgLedger, conn_id: Any,
                                                             clean_tables: Engine, clock: Clock) -> None:
    done = sync(ledger, spec(conn_id), [rec("k1", "1")])
    assert ledger.claim(done, "w1", 30) is None

    # Bounding attempts is the runner's job: waits and backfill chunks each take a claim.
    run_id, _ = ledger.create_run(spec(conn_id, day=1))
    for n in range(1, 8):
        lease = ledger.claim(run_id, "w1", 30)
        assert lease is not None
        ledger.wait(lease, clock.now, "retry")
        r = ledger.get_run(run_id)
        assert r is not None and (r.status, r.attempt) == (RunStatus.WAITING, n)
    lease = ledger.claim(run_id, "w1", 30)  # a waiting run moves back to running
    r = ledger.get_run(run_id)
    assert lease is not None and r is not None and (r.status, r.attempt) == (RunStatus.RUNNING, 8)


# --- checkpoint and raw -------------------------------------------------------------------------


def test_checkpoint_replaces_the_whole_checkpoint(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id, kind=RunKind.REPORT))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ledger.checkpoint(lease, Stage.REQUESTED, {"report_id": "rpt-1"})
    ledger.checkpoint(lease, Stage.FETCHING, {"page_seq": 3})
    r = row(clean_tables, "select stage, checkpoint from sync_runs where id = :id", id=run_id)
    assert r.stage == "fetching"
    assert r.checkpoint == {"page_seq": 3}  # the runner always writes all of it


def test_save_raw_is_idempotent_and_refuses_a_conflicting_entry(ledger: PgLedger, conn_id: Any,
                                                               clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    raw = ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10)
    assert ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10) == raw
    ledger.publish(lease, raw, [rec("k1", "1")])
    before = snapshot(clean_tables)
    with pytest.raises(IntegrityError):  # same page, other bytes: never rewrite what was published
        ledger.save_raw(lease, 0, "raw/0-refetch.json", SHA_B, 12)
    with pytest.raises(IntegrityError):  # another page cannot reuse a storage key
        ledger.save_raw(lease, 1, "raw/0.json", SHA_B, 12)
    assert snapshot(clean_tables) == before
    with pytest.raises(ValueError, match="sha256"):
        ledger.save_raw(lease, 1, "raw/1.json", "not-a-digest", 1)


# --- publish ------------------------------------------------------------------------------------


def test_newer_version_wins_and_a_stale_version_is_skipped(ledger: PgLedger, conn_id: Any,
                                                          clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    webhook = ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10)
    poll = ledger.save_raw(lease, 1, "raw/1.json", SHA_B, 10)
    assert ledger.publish(lease, webhook, [rec("o1", "2026-11-02T10:00:00Z", total=20)]).accepted == 1
    result = ledger.publish(lease, poll, [rec("o1", "2026-11-02T09:00:00Z", total=10),
                                          rec("o2", "2026-11-02T09:00:00Z", total=5)])
    assert (result.accepted, result.rejected, result.stale_skipped) == (1, 0, 1)
    stored = row(clean_tables, "select version, data from synced_records where record_key = 'o1'")
    assert stored.version == "2026-11-02T10:00:00Z" and stored.data["total"] == 20
    counts = row(clean_tables, "select records_accepted, records_rejected, records_stale from sync_runs"
                 " where id = :id", id=run_id)
    assert tuple(counts) == (2, 0, 1)


def test_versions_compare_in_byte_order_not_locale_order(ledger: PgLedger, conn_id: Any,
                                                         clean_tables: Engine) -> None:
    # Python (and the spec) say "B" < "a"; a locale collation says the opposite.
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    run_page(ledger, lease, 0, [rec("k", "a")])
    run_page(ledger, lease, 1, [rec("k", "B")])
    assert records(clean_tables) == {"k": ("a", False)}


def test_an_equal_version_replaces(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    run_page(ledger, lease, 0, [rec("k", "0005", total=1)])
    raw = ledger.save_raw(lease, 1, "raw/1.json", SHA_B, 10)
    assert ledger.publish(lease, raw, [rec("k", "0005", total=2)]).accepted == 1
    assert row(clean_tables, "select data from synced_records").data["total"] == 2


def test_publish_applies_records_in_order_and_rejects_bad_ones(ledger: PgLedger, conn_id: Any,
                                                              clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    raw = ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10)
    result = ledger.publish(lease, raw, [
        rec("k1", "0001"), rec("k1", "0003"), rec("k1", "0002"),  # in order: 0002 loses to 0003
        rec("", "0001"),  # no key
        Record(key="k2", version="0001", data={"x": float("nan")}),  # not JSON
        Record(key="k3", version="0001", data={"x": "nul\x00"}),  # Postgres can't store it
        rec("k4", "0001", deleted=True),  # a tombstone is a valid record
    ])
    assert (result.accepted, result.rejected, result.stale_skipped) == (3, 3, 1)
    assert records(clean_tables) == {"k1": ("0003", False), "k4": ("0001", True)}


def test_publish_retry_is_answered_from_the_receipt(ledger: PgLedger, conn_id: Any, clean_tables: Engine,
                                                    clock: Clock) -> None:
    s = spec(conn_id)
    run_id, _ = ledger.create_run(s)
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    raw = ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10)
    page = [rec("k1", "1"), rec("k2", "1")]
    first = ledger.publish(lease, raw, page)
    # The worker dies before checkpointing; a new attempt re-fetches the same bytes and publishes again.
    clock.advance(60)
    lease2 = ledger.claim(run_id, "w2", 30)
    assert lease2 is not None
    assert ledger.save_raw(lease2, 0, "raw/0.json", SHA_A, 10) == raw
    assert ledger.publish(lease2, raw, page) == first
    counts = row(clean_tables, "select records_accepted, records_stale from sync_runs where id = :id", id=run_id)
    assert tuple(counts) == (2, 0)  # not counted twice
    ledger.complete(lease2, s.window, snapshot_complete=False)
    assert ledger.verify_run(run_id)["records_accepted"] == 2


def test_publish_refuses_a_raw_object_from_another_run(ledger: PgLedger, conn_id: Any) -> None:
    a, _ = ledger.create_run(spec(conn_id))
    b, _ = ledger.create_run(spec(conn_id, dataset="refunds"))
    la, lb = ledger.claim(a, "w1", 30), ledger.claim(b, "w2", 30)
    assert la is not None and lb is not None
    raw = ledger.save_raw(la, 0, "raw/a0.json", SHA_A, 10)
    with pytest.raises(RawObjectMismatch):
        ledger.publish(lb, raw, [rec("k", "1")])


# --- complete, coverage and deletions -----------------------------------------------------------


def test_backlog_blocks_completion(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    s = spec(conn_id)
    run_id, _ = ledger.create_run(s)
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    first = ledger.save_raw(lease, 0, "raw/0.json", SHA_A, 10)
    second = ledger.save_raw(lease, 1, "raw/1.json", SHA_B, 10)
    ledger.publish(lease, first, [rec("k1", "1")])
    before = snapshot(clean_tables)
    with pytest.raises(BacklogPending, match="1 raw object"):
        ledger.complete(lease, s.window, snapshot_complete=True)
    assert snapshot(clean_tables) == before
    stream = row(clean_tables, "select covered_to from sync_streams")
    assert stream.covered_to is None  # coverage never runs ahead of published data

    ledger.publish(lease, second, [rec("k2", "1")])
    ledger.complete(lease, s.window, snapshot_complete=False)
    r = row(clean_tables, "select status, stage, finished_at from sync_runs where id = :id", id=run_id)
    assert (r.status, r.stage) == ("succeeded", "published") and r.finished_at is not None
    stream = row(clean_tables, "select covered_from, covered_to, last_publish_run_id, lease_run_id"
                 " from sync_streams")
    assert (stream.covered_from, stream.covered_to) == (s.window.start, s.window.end)
    assert (stream.last_publish_run_id, stream.lease_run_id) == (run_id, None)


def test_coverage_advances_only_contiguously(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    def covered() -> tuple[datetime, datetime]:
        s = row(clean_tables, "select covered_from, covered_to from sync_streams")
        return s.covered_from, s.covered_to

    sync(ledger, spec(conn_id, day=1), [rec("k", "1")])
    assert covered() == (T0 + DAY, T0 + 2 * DAY)
    sync(ledger, spec(conn_id, day=2), [rec("k", "2")])  # touches the end: extends
    assert covered() == (T0 + DAY, T0 + 3 * DAY)
    sync(ledger, spec(conn_id, day=0), [rec("k", "3")])  # a backfill touching the start: extends
    assert covered() == (T0, T0 + 3 * DAY)
    gap = sync(ledger, spec(conn_id, day=5), [rec("k", "4")])  # past a gap: no false coverage
    assert covered() == (T0, T0 + 3 * DAY)
    receipt = ledger.run_receipt(gap)
    assert receipt is not None and receipt["contiguous"] is False and receipt["coverage_advanced"] is False


def test_partial_snapshot_deletes_nothing(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    sync(ledger, spec(conn_id, day=0), [rec("a", "1"), rec("b", "1"), rec("c", "1")])
    # A truncated fetch saw only "a": not a complete snapshot, so nothing is inferred deleted.
    sync(ledger, spec(conn_id, day=1), [rec("a", "2")], snapshot_complete=False)
    assert records(clean_tables) == {"a": ("2", False), "b": ("1", False), "c": ("1", False)}


def test_complete_snapshot_tombstones_only_unseen_keys(ledger: PgLedger, conn_id: Any,
                                                       clean_tables: Engine) -> None:
    sync(ledger, spec(conn_id, day=0), [rec("a", "2"), rec("b", "1"), rec("c", "1")])
    # The snapshot sees "a" at an older version (it loses) and "b": both count as seen.
    run_id = sync(ledger, spec(conn_id, day=1), [rec("a", "1"), rec("b", "1")], snapshot_complete=True)
    assert records(clean_tables) == {"a": ("2", False), "b": ("1", False), "c": ("1", True)}
    receipt = ledger.run_receipt(run_id)
    assert receipt is not None and receipt["deletions_inferred"] == 1


def test_snapshot_with_rejected_records_deletes_nothing(ledger: PgLedger, conn_id: Any,
                                                        clean_tables: Engine) -> None:
    sync(ledger, spec(conn_id, day=0), [rec("a", "1"), rec("b", "1")])
    run_id = sync(ledger, spec(conn_id, day=1), [rec("a", "2"), rec("", "1")], snapshot_complete=True)
    assert records(clean_tables) == {"a": ("2", False), "b": ("1", False)}
    receipt = ledger.run_receipt(run_id)
    assert receipt is not None and receipt["deletion_skipped"] == "rejected_records"


def test_snapshot_without_any_page_deletes_nothing(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    sync(ledger, spec(conn_id, day=0), [rec("a", "1")])
    s = spec(conn_id, day=1)
    run_id, _ = ledger.create_run(s)
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ledger.complete(lease, s.window, snapshot_complete=True)
    assert records(clean_tables) == {"a": ("1", False)}


def test_replay_republishes_stored_raw_of_the_original_run(ledger: PgLedger, conn_id: Any,
                                                           clean_tables: Engine) -> None:
    original = sync(ledger, spec(conn_id), [rec("k", "1", total=1)])
    raw_id = row(clean_tables, "select id from raw_objects where run_id = :id", id=original).id
    replay_id = ledger.create_replay(original, "synthetic-2")
    lease = ledger.claim(replay_id, "w1", 30)
    assert lease is not None
    # A fixed parser produces different data at the same version; the replay rewrites it.
    assert ledger.publish(lease, raw_id, [rec("k", "1", total=2)]).accepted == 1
    ledger.complete(lease, spec(conn_id).window, snapshot_complete=False)
    assert row(clean_tables, "select data from synced_records").data["total"] == 2


# --- wait, fail and receipts --------------------------------------------------------------------


def test_wait_stores_a_sanitized_reason_and_releases_the_stream(ledger: PgLedger, conn_id: Any,
                                                                clean_tables: Engine, clock: Clock) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 300)
    assert lease is not None
    until = clock.now + timedelta(minutes=5)
    ledger.wait(lease, until, "429 for Authorization: Bearer synthetic-opaque-token-0123456789", request_ref="req-42")
    r = row(clean_tables, "select status, next_attempt_at, wait_reason, provider_request_ref"
            " from sync_runs where id = :id", id=run_id)
    assert (r.status, r.next_attempt_at, r.provider_request_ref) == ("waiting", until, "req-42")
    assert "synthetic-opaque" not in r.wait_reason and "[redacted]" in r.wait_reason
    again = ledger.claim(run_id, "w2", 30)  # the lease was released: no need to wait for expiry
    assert again is not None and again.fence == lease.fence + 1


def test_fail_stores_sanitized_detail_and_is_terminal(ledger: PgLedger, conn_id: Any,
                                                       clean_tables: Engine) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ledger.fail(lease, "Permanent", "upstream 400 access_token=abc123\nmore", "req 2/€")
    r = row(clean_tables, "select status, next_attempt_at, error_code, error_detail, provider_request_ref,"
            " finished_at from sync_runs where id = :id", id=run_id)
    assert (r.status, r.next_attempt_at, r.error_code) == ("failed", None, "permanent")
    assert r.error_detail == "upstream 400 access_token=[redacted] more"
    assert r.provider_request_ref == "req2/" and r.finished_at is not None
    assert ledger.claim(run_id, "w1", 30) is None


def test_sanitize_detail_redacts_secrets_and_caps_length() -> None:
    token = "ya29." + "x" * 40
    out = sanitize_detail(f'{{"refresh_token": "{token}"}} api_key=k-123 run {uuid.UUID(int=1)}\n' + "z" * 900)
    assert out is not None
    assert token not in out and "k-123" not in out and "\n" not in out
    assert str(uuid.UUID(int=1)) in out  # ids stay readable for operators
    assert len(out) <= 500


def test_verify_run_detects_a_tampered_receipt(ledger: PgLedger, conn_id: Any, clean_tables: Engine) -> None:
    run_id = sync(ledger, spec(conn_id), [rec("k", "1")])
    assert ledger.verify_run(run_id)["run_id"] == str(run_id)
    with clean_tables.begin() as conn:
        conn.execute(text("update raw_objects set receipt = jsonb_set(receipt, '{accepted}', '9')"))
    with pytest.raises(ReceiptMismatch):
        ledger.verify_run(run_id)



# --- reads and replays --------------------------------------------------------------------------


def test_get_run_reads_back_the_spec_and_progress(ledger: PgLedger, conn_id: Any) -> None:
    s = spec(conn_id, kind=RunKind.BACKFILL, trigger=Trigger.MANUAL)
    run_id, _ = ledger.create_run(s)
    view = ledger.get_run(run_id)
    assert view is not None
    assert (view.spec, view.status, view.stage, view.attempt, view.max_attempts, view.replay_of) == (
        s, RunStatus.QUEUED, Stage.PENDING, 0, 5, None)
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ledger.checkpoint(lease, Stage.FETCHING, {"cursor": "c2"})
    view = ledger.get_run(run_id)
    assert view is not None and (view.status, view.stage, view.checkpoint, view.attempt) == (
        RunStatus.RUNNING, Stage.FETCHING, {"cursor": "c2"}, 1)
    assert ledger.get_run(uuid.uuid4()) is None


def test_raw_objects_are_listed_in_page_order(ledger: PgLedger, conn_id: Any) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ids = {seq: ledger.save_raw(lease, seq, f"raw/{seq}.json", f"{seq:064x}", seq + 1) for seq in (2, 0, 1)}
    ledger.publish(lease, ids[1], [rec("k", "1")])
    raws = ledger.raw_objects(run_id)
    assert [(r.page_seq, r.id, r.size, r.processed) for r in raws] == [
        (0, ids[0], 1, False), (1, ids[1], 2, True), (2, ids[2], 3, False)]
    assert raws[0].storage_key == "raw/0.json" and raws[0].sha256 == f"{0:064x}"
    assert ledger.raw_objects(uuid.uuid4()) == []


def test_create_replay_makes_a_separate_queued_run_each_time(ledger: PgLedger, conn_id: Any,
                                                            clean_tables: Engine) -> None:
    s = spec(conn_id, day=3)
    original = sync(ledger, s, [rec("k", "1")])
    first = ledger.create_replay(original, "synthetic-2", requested_by="user-1")
    second = ledger.create_replay(original, "synthetic-2")
    assert first != second
    view = ledger.get_run(first)
    assert view is not None
    assert (view.status, view.spec.kind, view.spec.window, view.spec.connector_version, view.replay_of) == (
        RunStatus.QUEUED, RunKind.REPLAY, s.window, "synthetic-2", original)
    r = row(clean_tables, "select requested_by, enqueued_at, trigger from sync_runs where id = :id", id=first)
    assert (r.requested_by, r.enqueued_at, r.trigger) == ("user-1", None, "manual")  # an outbox row
    again = ledger.get_run(ledger.create_replay(first, "synthetic-3"))  # a replay of a replay
    assert again is not None and again.replay_of == original  # points at the run that owns the raw
    with pytest.raises(RunNotFound):
        ledger.create_replay(uuid.uuid4(), "synthetic-2")


def test_wait_leaves_the_queue_job_alone(ledger: PgLedger, conn_id: Any, clean_tables: Engine,
                                         clock: Clock) -> None:
    run_id, _ = ledger.create_run(spec(conn_id))
    with clean_tables.begin() as conn:
        conn.execute(text("update sync_runs set enqueued_at = now(), queue_job_id = 41 where id = :id"),
                     {"id": run_id})
    lease = ledger.claim(run_id, "w1", 30)
    assert lease is not None
    ledger.wait(lease, clock.now + timedelta(seconds=30), "retry")
    r = row(clean_tables, "select status, queue_job_id, enqueued_at from sync_runs where id = :id", id=run_id)
    assert (r.status, r.queue_job_id) == ("waiting", 41) and r.enqueued_at is not None
