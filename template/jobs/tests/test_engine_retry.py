import random
from datetime import UTC, datetime, timedelta

import pytest

from jobs.sync.retry import (
    RetryPolicy,
    backoff_s,
    ceiling_s,
    next_attempt_at,
    next_delay_s,
    parse_retry_after,
)

NOW = datetime(2026, 11, 25, 12, 0, tzinfo=UTC)


def seeded(seed: int) -> random.Random:
    return random.Random(seed)  # noqa: S311  (jitter draws, seeded so the tests repeat)

POLICY = RetryPolicy(base_s=2, cap_s=60, max_attempts=5)


def test_ceiling_doubles_then_caps() -> None:
    assert [ceiling_s(a, POLICY) for a in range(1, 8)] == [2, 4, 8, 16, 32, 60, 60]
    assert ceiling_s(10_000, POLICY) == 60  # no overflow on absurd attempt counts


def test_full_jitter_stays_between_zero_and_the_ceiling_and_spreads() -> None:
    rng = seeded(7)
    draws = [backoff_s(4, POLICY, rng) for _ in range(2000)]
    assert all(0 <= d <= 16 for d in draws)
    assert min(draws) < 1 and max(draws) > 15  # really spread, not a fixed delay
    assert 7 < sum(draws) / len(draws) < 9  # uniform: mean is half the ceiling


def test_attempts_are_bounded() -> None:
    rng = seeded(1)
    assert next_delay_s(4, policy=POLICY, rng=rng) is not None
    assert next_delay_s(5, policy=POLICY, rng=rng) is None
    assert next_attempt_at(NOW, 5, policy=POLICY) is None
    assert next_delay_s(1, policy=RetryPolicy(max_attempts=1)) is None


def test_retry_after_is_a_floor_not_a_ceiling() -> None:
    rng = seeded(3)
    for _ in range(200):
        assert next_delay_s(1, retry_after_s=30, policy=POLICY, rng=rng) == 30  # ceiling 2 < 30
    # A short Retry-After never shortens a longer backoff draw.
    delays = [next_delay_s(5 - 1, retry_after_s=0.5, policy=POLICY, rng=rng) for _ in range(200)]
    assert all(d is not None and d >= 0.5 for d in delays)
    assert any(d is not None and d > 0.5 for d in delays)


def test_next_attempt_at_adds_the_delay() -> None:
    at = next_attempt_at(NOW, 1, retry_after_s=90, policy=POLICY, rng=seeded(0))
    assert at == NOW + timedelta(seconds=90)


@pytest.mark.parametrize(("header", "expected"), [
    ("120", 120.0), (" 0 ", 0.0), ("1.5", 1.5), ("-4", 0.0),
    ("Wed, 25 Nov 2026 12:01:00 GMT", 60.0),
    ("Wed, 25 Nov 2026 11:00:00 GMT", 0.0),  # in the past: retry now, never negative
    (None, None), ("", None), ("soon", None),
])
def test_parse_retry_after(header: str | None, expected: float | None) -> None:
    assert parse_retry_after(header, NOW) == expected


def test_policy_rejects_nonsense() -> None:
    with pytest.raises(ValueError, match="RetryPolicy"):
        RetryPolicy(base_s=0)
    with pytest.raises(ValueError, match="RetryPolicy"):
        RetryPolicy(base_s=10, cap_s=5)
    with pytest.raises(ValueError, match="1-based"):
        ceiling_s(0)
