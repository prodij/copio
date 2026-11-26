import threading
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import Engine, text

from jobs.sync.budgets import Budgets, PgRateBudgets, UnknownBudget
from jobs.sync.contract import RateBudgets

T0 = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)
KEY = "synthetic:acct-1"


@pytest.fixture
def budgets(clean_tables: Engine) -> Budgets:
    b = Budgets(clean_tables)
    b.ensure(KEY, capacity=5, refill_per_s=1)
    with clean_tables.begin() as conn:  # pin the bucket's clock to T0
        conn.execute(text("update rate_budgets set updated_at = :t"), {"t": T0})
    return b


def _tokens(engine: Engine) -> float:
    with engine.connect() as conn:
        return float(conn.execute(text("select tokens from rate_budgets where budget_key = :k"),
                                  {"k": KEY}).scalar_one())


def test_exhaustion_then_refill(budgets: Budgets, clean_tables: Engine) -> None:
    for _ in range(5):
        assert budgets.acquire(KEY, now=T0).ok
    denied = budgets.acquire(KEY, now=T0)
    assert not denied.ok and denied.wait_s == pytest.approx(1.0)
    assert denied.blocked_until is None
    assert _tokens(clean_tables) == 0  # a denied acquire spends nothing
    assert budgets.acquire(KEY, now=T0 + timedelta(seconds=1)).ok
    # Refill is capped at capacity, however long the bucket sat idle.
    assert budgets.acquire(KEY, cost=5, now=T0 + timedelta(hours=1)).ok
    assert not budgets.acquire(KEY, now=T0 + timedelta(hours=1)).ok


def test_a_cost_larger_than_the_bucket_is_an_error(budgets: Budgets) -> None:
    with pytest.raises(ValueError, match="exceeds the capacity"):
        budgets.acquire(KEY, cost=6, now=T0)


def test_429_blocks_until_retry_after_and_never_shortens(budgets: Budgets) -> None:
    until = budgets.block(KEY, retry_after_s=30, now=T0)
    assert until == T0 + timedelta(seconds=30)
    blocked = budgets.acquire(KEY, now=T0 + timedelta(seconds=10))
    assert not blocked.ok and blocked.blocked_until == until and blocked.wait_s == pytest.approx(20)
    # A later, shorter Retry-After keeps the longer block.
    assert budgets.block(KEY, retry_after_s=5, now=T0 + timedelta(seconds=10)) == until
    # The bucket refills from empty starting when the block ends: no burst of saved-up tokens.
    assert not budgets.acquire(KEY, now=until).ok
    assert budgets.acquire(KEY, cost=1, now=until + timedelta(seconds=1)).ok
    assert not budgets.acquire(KEY, cost=2, now=until + timedelta(seconds=1)).ok


def test_block_without_retry_after_uses_the_default(budgets: Budgets) -> None:
    assert budgets.block(KEY, retry_after_s=None, now=T0, default_s=60) == T0 + timedelta(seconds=60)


def test_unknown_budget_is_never_unlimited(clean_tables: Engine) -> None:
    b = Budgets(clean_tables)
    with pytest.raises(UnknownBudget):
        b.acquire("synthetic:typo", now=T0)
    with pytest.raises(UnknownBudget):
        b.block("synthetic:typo", retry_after_s=1, now=T0)
    assert b.acquire("synthetic:new", capacity=2, refill_per_s=0.5).ok  # created full on first use


def test_concurrent_acquires_never_overspend(budgets: Budgets, clean_tables: Engine) -> None:
    with clean_tables.begin() as conn:
        conn.execute(text("update rate_budgets set capacity = 20, tokens = 20, refill_per_s = 0.000001"))
    barrier = threading.Barrier(10)
    granted: list[bool] = []
    lock = threading.Lock()

    def worker() -> None:
        barrier.wait()
        for _ in range(5):
            ok = budgets.acquire(KEY, now=T0).ok
            with lock:
                granted.append(ok)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert granted.count(True) == 20 and len(granted) == 50
    assert _tokens(clean_tables) == pytest.approx(0, abs=1e-3)


# -- contract.RateBudgets, as the runner uses it ---------------------------------------------------


def test_pg_rate_budgets_satisfies_the_contract(clean_tables: Engine) -> None:
    budgets: RateBudgets = PgRateBudgets(clean_tables)
    assert budgets.blocked_until("synthetic:fresh") is None


def test_block_creates_a_missing_bucket_blocked_and_empty(clean_tables: Engine) -> None:
    rb = PgRateBudgets(clean_tables, default_capacity=10, default_refill_per_s=2)
    until = T0 + timedelta(seconds=30)
    rb.block("synthetic:new", until)  # a 429 before anyone ever acquired from this scope
    assert rb.blocked_until("synthetic:new") == until
    b = Budgets(clean_tables)
    assert b.acquire("synthetic:new", now=T0 + timedelta(seconds=10)).blocked_until == until
    assert not b.acquire("synthetic:new", now=until).ok  # empty when the block ends
    assert b.acquire("synthetic:new", cost=2, now=until + timedelta(seconds=1)).ok  # default refill 2/s


def test_a_later_block_never_shortens_an_existing_one(budgets: Budgets, clean_tables: Engine) -> None:
    rb = PgRateBudgets(clean_tables)
    long, short = T0 + timedelta(minutes=5), T0 + timedelta(seconds=10)
    rb.block(KEY, long)
    rb.block(KEY, short)
    assert rb.blocked_until(KEY) == long
    rb.block(KEY, long + timedelta(minutes=1))
    assert rb.blocked_until(KEY) == long + timedelta(minutes=1)
    # The existing bucket keeps its capacity; it is only emptied.
    with clean_tables.connect() as conn:
        assert conn.execute(text("select capacity, tokens from rate_budgets where budget_key = :k"),
                            {"k": KEY}).one() == (5, 0)
    # Budgets.block and PgRateBudgets.block share one row and one rule.
    assert budgets.block(KEY, retry_after_s=1, now=T0) == long + timedelta(minutes=1)


def test_blocked_until_returns_a_past_block_as_stored(clean_tables: Engine) -> None:
    rb = PgRateBudgets(clean_tables)
    rb.block(KEY, T0)
    assert rb.blocked_until(KEY) == T0  # the runner compares with its own clock


def test_block_needs_an_aware_time(clean_tables: Engine) -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        PgRateBudgets(clean_tables).block(KEY, datetime(2026, 11, 25, 12))
