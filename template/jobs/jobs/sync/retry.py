"""When to try a failed unit of work again. Pure functions: no clock, no database, no sleeping.

Exponential backoff with full jitter (a uniform draw between 0 and the exponential ceiling), so many
workers that failed together don't come back together. A provider's Retry-After is a floor: we never
come back sooner than the provider asked. Attempts are bounded: past `max_attempts` there is no next
attempt and the run fails for an operator or a new trigger.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime


@dataclass(frozen=True)
class RetryPolicy:
    base_s: float = 2.0  # ceiling of the first retry's delay
    cap_s: float = 900.0  # the exponential ceiling never grows past this
    max_attempts: int = 5  # attempts in all, the first one included

    def __post_init__(self) -> None:
        if self.base_s <= 0 or self.cap_s < self.base_s or self.max_attempts < 1:
            raise ValueError("RetryPolicy needs 0 < base_s <= cap_s and max_attempts >= 1")


DEFAULT_POLICY = RetryPolicy()


def ceiling_s(attempt: int, policy: RetryPolicy = DEFAULT_POLICY) -> float:
    """The most we wait after the `attempt`-th failed attempt (1-based): base * 2^(attempt-1), capped."""
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    # min() before the power would overflow on a huge attempt count.
    exponent = min(attempt - 1, 64)
    return float(min(policy.cap_s, policy.base_s * (2.0**exponent)))


def backoff_s(attempt: int, policy: RetryPolicy = DEFAULT_POLICY,
              rng: random.Random | None = None) -> float:
    """Full jitter: uniform in [0, ceiling]."""
    draw = (rng or random.Random()).random()  # noqa: S311  (jitter, not security)
    return draw * ceiling_s(attempt, policy)


def next_delay_s(attempt: int, *, retry_after_s: float | None = None,
                 policy: RetryPolicy = DEFAULT_POLICY, rng: random.Random | None = None) -> float | None:
    """Seconds to wait before the next attempt, after `attempt` attempts have failed. None: give up."""
    if attempt >= policy.max_attempts:
        return None
    delay = backoff_s(attempt, policy, rng)
    if retry_after_s is not None and retry_after_s > delay:
        delay = retry_after_s
    return delay


def next_attempt_at(now: datetime, attempt: int, *, retry_after_s: float | None = None,
                    policy: RetryPolicy = DEFAULT_POLICY,
                    rng: random.Random | None = None) -> datetime | None:
    delay = next_delay_s(attempt, retry_after_s=retry_after_s, policy=policy, rng=rng)
    return None if delay is None else now + timedelta(seconds=delay)


def parse_retry_after(value: str | None, now: datetime) -> float | None:
    """An HTTP Retry-After header (delta-seconds or an HTTP date) as seconds from `now`, never negative.
    None when absent or unreadable: the caller then relies on backoff alone."""
    if value is None or not value.strip():
        return None
    text = value.strip()
    try:
        return max(0.0, float(text))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - now).total_seconds())
