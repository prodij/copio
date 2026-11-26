"""Scenario 4: 429, timeout, 5xx.

Must observe: bounded retries with provider-aware delay and jitter; no busy loop."""

import itertools
import logging

import pytest

from jobs.sync.contract import RunStatus
from jobs.sync.runner import Outcome
from jobs.sync.testing import Fault, FaultPlan, FaultRule

from . import thresholds as T
from .harness import Harness


def _gaps(h: Harness) -> list[float]:
    """Seconds between one execution finishing and the next one starting."""
    hist = h.engine.history
    return [(b.at - a.finished_at).total_seconds() for a, b in itertools.pairwise(hist)]


def test_429_waits_at_least_retry_after_and_blocks_the_budget(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.RATE_LIMITED, at_call=1, retry_after_s=20.0)])
    run_id = h.submit(h.spec())
    h.drain()

    assert h.run(run_id).status is RunStatus.SUCCEEDED
    [gap] = _gaps(h)
    assert 20.0 <= gap <= 20.0 * (1 + T.RATE_LIMIT_JITTER_FRACTION)
    [(key, _until)] = h.budgets.blocks
    assert key.endswith(str(h.spec().connection_id))
    assert h.waits(run_id) == ["rate_limited"]


def test_429_without_retry_after_uses_the_default(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.RATE_LIMITED, at_call=1, retry_after_s=None)])
    h.submit(h.spec())
    h.drain()
    [gap] = _gaps(h)
    assert gap >= T.RATE_LIMIT_DEFAULT_S


@pytest.mark.parametrize("fault", [Fault.TIMEOUT, Fault.SERVER_ERROR])
def test_transient_errors_retry_with_backoff_then_succeed(implementations: Harness, fault: Fault) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(fault, at_call=1, times=2)])
    run_id = h.submit(h.spec())
    h.drain()

    assert h.run(run_id).status is RunStatus.SUCCEEDED
    assert h.feed.call_count == 3
    gaps = _gaps(h)
    assert len(gaps) == 2
    assert all(T.MIN_RETRY_DELAY_S <= g <= T.RETRY_CAP_S for g in gaps)  # never a busy loop


def test_persistent_5xx_fails_after_max_attempts(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.SERVER_ERROR, at_call=1, times=1000)])
    run_id = h.submit(h.spec())
    h.drain()

    row = h.run_row(run_id)
    assert row.status is RunStatus.FAILED
    assert row.error_code == "transient_exhausted"
    assert h.feed.call_count == T.MAX_ATTEMPTS
    assert len(h.engine.history) == T.MAX_ATTEMPTS
    gaps = _gaps(h)
    assert all(g >= T.MIN_RETRY_DELAY_S for g in gaps)
    assert len(set(gaps)) > 1  # jittered, not lockstep
    assert h.coverage() == (None, None)


def test_persistent_429_fails_boundedly(implementations: Harness) -> None:
    h = implementations
    h.feed.faults = FaultPlan([FaultRule(Fault.RATE_LIMITED, at_call=1, times=1000, retry_after_s=2.0)])
    run_id = h.submit(h.spec())
    h.drain()

    assert h.run_row(run_id).error_code == "rate_limit_exhausted"
    assert h.feed.call_count == T.MAX_RATE_LIMIT_WAITS + 1


@pytest.mark.parametrize("fault", [Fault.RATE_LIMITED, Fault.TIMEOUT, Fault.SERVER_ERROR,
                                   Fault.AUTH_REVOKED, Fault.MISSING_PAGE])
def test_errors_never_carry_secrets_or_payloads(implementations: Harness, fault: Fault,
                                                caplog: pytest.LogCaptureFixture) -> None:
    h = implementations
    caplog.set_level(logging.DEBUG)
    h.feed.faults = FaultPlan([FaultRule(fault, at_call=1, times=1000, retry_after_s=1.0)])
    token = h.credentials.get(h.spec().connection_id).access_token
    run_id = h.submit(h.spec())
    h.drain()

    row = h.run_row(run_id)
    assert row.status is RunStatus.FAILED
    for text in (row.error_detail or "", row.provider_request_ref or "", caplog.text):
        assert token not in text
        assert "tok-" not in text
        assert "amount" not in text
    assert row.provider_request_ref and row.provider_request_ref.startswith("req-")
    assert Outcome.FAILED in [e.outcome for e in h.engine.history]
