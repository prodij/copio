"""Provider quota as token buckets in `rate_budgets`, shared by every worker.

One row per provider quota scope (`budget_key`, e.g. "synthetic:<account>"), because that is what the
provider counts against, not our connection or dataset. `acquire` is a single UPDATE: Postgres locks
the row and re-checks the WHERE clause after any concurrent update, so two workers can never spend the
same token. A provider 429 calls `block`, which empties the bucket and sets `blocked_until`; nothing
acquires before then.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine, text


class UnknownBudget(KeyError):
    """No `rate_budgets` row for this key, and no capacity given to create one."""


@dataclass(frozen=True)
class Acquired:
    ok: bool
    wait_s: float  # 0 when ok; else how long until the bucket could pay `cost`
    blocked_until: datetime | None = None  # set when a provider block is why


# Refill since the last update, capped at capacity. `:now` is bound by the caller so tests control time;
# greatest(0, ...) keeps a clock that went backwards from draining the bucket.
_ACQUIRE = text("""
    update rate_budgets
       set tokens = least(capacity, tokens + refill_per_s * greatest(0, extract(epoch from (:now - updated_at)))) - :cost,
           updated_at = greatest(updated_at, :now)
     where budget_key = :key
       and (blocked_until is null or blocked_until <= :now)
       and least(capacity, tokens + refill_per_s * greatest(0, extract(epoch from (:now - updated_at)))) >= :cost
    returning tokens
""")

_PEEK = text("""
    select least(capacity, tokens + refill_per_s * greatest(0, extract(epoch from (:now - updated_at)))) as available,
           refill_per_s, capacity, blocked_until
      from rate_budgets where budget_key = :key
""")


class Budgets:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def ensure(self, key: str, *, capacity: float, refill_per_s: float) -> None:
        """Create the bucket full if it doesn't exist. An existing bucket keeps its state."""
        if capacity <= 0 or refill_per_s <= 0:
            raise ValueError("capacity and refill_per_s must be positive")
        with self.engine.begin() as conn:
            conn.execute(text(
                "insert into rate_budgets (budget_key, capacity, refill_per_s, tokens, updated_at)"
                " values (:key, :capacity, :refill, :capacity, now()) on conflict (budget_key) do nothing"),
                {"key": key, "capacity": capacity, "refill": refill_per_s})

    def acquire(self, key: str, cost: float = 1.0, *, now: datetime | None = None,
                capacity: float | None = None, refill_per_s: float | None = None) -> Acquired:
        """Take `cost` tokens, or say how long to wait. Never blocks or sleeps.

        With `capacity` and `refill_per_s`, a missing bucket is created first; without them it raises
        UnknownBudget, so a typo in a key can't mean "unlimited"."""
        if cost <= 0:
            raise ValueError("cost must be positive")
        now = now or datetime.now(UTC)
        if capacity is not None and refill_per_s is not None:
            self.ensure(key, capacity=capacity, refill_per_s=refill_per_s)
        params = {"key": key, "cost": cost, "now": now}
        with self.engine.begin() as conn:
            if conn.execute(_ACQUIRE, params).first() is not None:
                return Acquired(ok=True, wait_s=0.0)
            row = conn.execute(_PEEK, params).first()
        if row is None:
            raise UnknownBudget(key)
        if row.blocked_until is not None and row.blocked_until > now:
            return Acquired(ok=False, wait_s=(row.blocked_until - now).total_seconds(),
                            blocked_until=row.blocked_until)
        if cost > row.capacity:
            raise ValueError(f"cost {cost} exceeds the capacity of {key}")
        return Acquired(ok=False, wait_s=max(0.0, (cost - float(row.available)) / float(row.refill_per_s)))

    def block(self, key: str, *, retry_after_s: float | None, now: datetime | None = None,
              default_s: float = 60.0) -> datetime:
        """A provider said 429: empty the bucket and refuse every acquire until the provider's time.
        The bucket starts refilling from empty at that time, not during the block, so work resumes at
        the normal rate instead of a burst. A later, shorter Retry-After never shortens an existing
        block. Returns the effective time."""
        now = now or datetime.now(UTC)
        until = now + timedelta(seconds=retry_after_s if retry_after_s is not None else default_s)
        with self.engine.begin() as conn:
            row = conn.execute(text(
                "update rate_budgets set tokens = 0, updated_at = greatest(updated_at, :until),"
                " blocked_until = greatest(coalesce(blocked_until, :until), :until)"
                " where budget_key = :key returning blocked_until"),
                {"key": key, "now": now, "until": until}).first()
        if row is None:
            raise UnknownBudget(key)
        blocked: datetime = row.blocked_until
        return blocked


class PgRateBudgets:
    """contract.RateBudgets on `rate_budgets`: the slice the runner uses.

    `blocked_until` returns the stored time as is (the runner compares it with its own clock).
    `block` works for a key nobody created yet: a provider can 429 before any acquire, so a missing
    bucket is created blocked and empty with the default capacity. Like `Budgets.block`, a later block
    never shortens an existing one, and refill starts when the block ends.
    """

    def __init__(self, engine: Engine, *, default_capacity: float = 60.0,
                 default_refill_per_s: float = 1.0) -> None:
        if default_capacity <= 0 or default_refill_per_s <= 0:
            raise ValueError("default_capacity and default_refill_per_s must be positive")
        self.engine = engine
        self.default_capacity = default_capacity
        self.default_refill_per_s = default_refill_per_s

    def blocked_until(self, budget_key: str) -> datetime | None:
        with self.engine.connect() as conn:
            value: datetime | None = conn.execute(
                text("select blocked_until from rate_budgets where budget_key = :key"),
                {"key": budget_key}).scalar_one_or_none()
        return value

    def block(self, budget_key: str, until: datetime) -> None:
        if until.tzinfo is None:
            raise ValueError("until must be timezone-aware")
        with self.engine.begin() as conn:
            conn.execute(text("""
                insert into rate_budgets (budget_key, capacity, refill_per_s, tokens, blocked_until, updated_at)
                values (:key, :capacity, :refill, 0, :until, :until)
                on conflict (budget_key) do update
                   set tokens = 0,
                       blocked_until = greatest(coalesce(rate_budgets.blocked_until, excluded.blocked_until),
                                                excluded.blocked_until),
                       updated_at = greatest(rate_budgets.updated_at, excluded.blocked_until)
            """), {"key": budget_key, "capacity": self.default_capacity,
                   "refill": self.default_refill_per_s, "until": until})
