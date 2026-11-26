"""Deterministic fault injection. A rule fires on a numbered provider call, so runs are repeatable."""

from __future__ import annotations

import enum
from collections.abc import Sequence
from dataclasses import dataclass, field

from jobs.sync.contract import (
    AuthRevoked,
    PermanentError,
    RateLimited,
    TransientError,
)


class Fault(enum.StrEnum):
    RATE_LIMITED = "rate_limited"  # 429 with Retry-After (or without, if retry_after_s is None)
    TIMEOUT = "timeout"
    SERVER_ERROR = "server_error"  # 5xx
    AUTH_REVOKED = "auth_revoked"
    SCHEMA_CHANGE = "schema_change"  # the body arrives in a shape this connector version can't parse
    MISSING_PAGE = "missing_page"  # the cursor points at a page the provider no longer has
    PARTIAL_SNAPSHOT = "partial_snapshot"  # a snapshot ends early and says it is not complete
    STALE_READ = "stale_read"  # out-of-order versions: the page serves an older version
    DUPLICATE = "duplicate"  # the page repeats the previous page's records too


class SchemaChanged(PermanentError):
    """The body no longer matches what this connector version parses. Carries the raw body
    (`ProviderError.raw`) so the runner keeps it for a replay after the connector is fixed."""

    def __init__(self, message: str, *, raw: bytes, request_ref: str | None = None) -> None:
        super().__init__(message, request_ref=request_ref, raw=raw)


@dataclass(frozen=True)
class FaultRule:
    """Fire `fault` on provider calls number at_call .. at_call + times - 1 (1-based).

    `operation` limits the rule to one call type ("fetch_page", "request_report", "report_status",
    "download", "refresh_token"); None matches any call."""

    fault: Fault
    at_call: int
    times: int = 1
    retry_after_s: float | None = 5.0
    operation: str | None = None

    def matches(self, call_no: int, operation: str) -> bool:
        if self.operation is not None and self.operation != operation:
            return False
        return self.at_call <= call_no < self.at_call + self.times


@dataclass
class FaultPlan:
    rules: Sequence[FaultRule] = field(default_factory=tuple)

    def active(self, call_no: int, operation: str) -> Fault | None:
        rule = self.rule(call_no, operation)
        return rule.fault if rule else None

    def rule(self, call_no: int, operation: str) -> FaultRule | None:
        for rule in self.rules:
            if rule.matches(call_no, operation):
                return rule
        return None


# The synthetic provider's error messages deliberately include the token and a payload fragment, so the
# contract suite can prove the runner never copies a provider message into a log or error_detail.
def raise_for(rule: FaultRule, *, token: str, budget_key: str, request_ref: str) -> None:
    secretish = f"token={token} body={{\"amount\": 1}}"
    if rule.fault is Fault.RATE_LIMITED:
        raise RateLimited(f"429 Too Many Requests {secretish}", retry_after_s=rule.retry_after_s,
                          budget_key=budget_key, request_ref=request_ref)
    if rule.fault is Fault.TIMEOUT:
        raise TransientError(f"read timeout {secretish}", request_ref=request_ref)
    if rule.fault is Fault.SERVER_ERROR:
        raise TransientError(f"503 Service Unavailable {secretish}", request_ref=request_ref)
    if rule.fault is Fault.AUTH_REVOKED:
        raise AuthRevoked(f"401 token revoked {secretish}", request_ref=request_ref)
    if rule.fault is Fault.MISSING_PAGE:
        raise PermanentError(f"404 page not found {secretish}", request_ref=request_ref)
