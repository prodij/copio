"""SP-API client error mapping — every failure mode must surface as a named
exception per the Error & Rescue Map. NO `except Exception:` allowed.
"""
import pytest

from copio_api.integrations.spapi import (
    SPAPIBadResponse,
    SPAPIClient,
    SPAPIPermissionDenied,
    SPAPIRateLimit,
    SPAPIUpstreamDown,
)


class FakeException(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


@pytest.mark.parametrize(
    "fake_status,fake_message,expected_cls",
    [
        (429, "QuotaExceeded", SPAPIRateLimit),
        (None, "ThrottleException raised", SPAPIRateLimit),
        (401, "Unauthorized", SPAPIPermissionDenied),
        (403, "Forbidden", SPAPIPermissionDenied),
        (502, "Bad Gateway", SPAPIUpstreamDown),
        (503, "Service Unavailable", SPAPIUpstreamDown),
        (400, "ValidationException", SPAPIBadResponse),
        (None, "schema mismatch", SPAPIBadResponse),
    ],
)
def test_raise_named_maps_correctly(fake_status, fake_message, expected_cls) -> None:
    exc = FakeException(fake_message, status=fake_status)
    with pytest.raises(expected_cls):
        SPAPIClient._raise_named("orders", exc)


def test_cache_key_is_stable_within_a_day() -> None:
    """Cache hit depends on (endpoint, params, day) — same call on the same
    day must collide."""
    from copio_api.integrations.spapi.client import SPAPISession

    session = SPAPISession(
        refresh_token="x", seller_id="y", marketplace_id="ATVPDKIKX0DER"
    )
    client = SPAPIClient(session)
    k1 = client._cache_key("orders", {"asin": "B0CABCD123", "days": 30})
    k2 = client._cache_key("orders", {"days": 30, "asin": "B0CABCD123"})
    assert k1 == k2, "cache key must be order-independent (sorted params)"


def test_ttl_buckets() -> None:
    from copio_api.integrations.spapi.client import SPAPISession

    session = SPAPISession(
        refresh_token="x", seller_id="y", marketplace_id="ATVPDKIKX0DER"
    )
    client = SPAPIClient(session)
    assert client._ttl_for("orders") == client.HOT_TTL
    assert client._ttl_for("fba_inventory") == client.HOT_TTL
    assert client._ttl_for("reports") == client.COLD_TTL
