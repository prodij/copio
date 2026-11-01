import base64
import itertools
import json
import logging
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import httpx
import jwt
import pytest
import respx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.billing.models import Subscription, WebhookEvent
from app.billing.webhooks import (
    LAGO_WEBHOOK_TYPES,
    WebhookVerifier,
    _verifier,
    get_webhook_verifier,
    handle_event,
)
from app.config import Settings
from app.db import engine_for
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.models import Workspace
from tests.fakes import LAGO

ISSUER = "http://lago.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
FIXTURES = Path(__file__).parent / "fixtures" / "lago"
_TICKS = itertools.count(1)


def fixture(name: str) -> dict[str, Any]:
    """A webhook body shaped like lago-api v1.55.0 sends it (see tests/fixtures/lago)."""
    result: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return result


def app_of(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def make_sub(db_session: Session, lago_id: bool = True, state: str = "pending") -> Subscription:
    """A checkout attempt; `lago_id=False`: saved before the Lago create returned."""
    ws = Workspace(name="Acme", owner_user_id=f"u-{uuid.uuid4()}", status="ready")
    db_session.add(ws)
    db_session.flush()
    attempt = f"{ws.id}:starter:{uuid.uuid4().hex[:8]}"
    s = Subscription(workspace_id=ws.id, plan_code="starter", state=state, lago_external_id=attempt,
                     lago_subscription_id=attempt if lago_id else None)
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def sub(db_session: Session, client: TestClient) -> Subscription:
    app_of(client).dependency_overrides[get_webhook_verifier] = lambda: WebhookVerifier(PEM, ISSUER)
    return make_sub(db_session)


def sign(payload: dict[str, Any], sign_with: object = KEY, issuer: str = ISSUER) -> str:
    return jwt.encode({"data": json.dumps(payload), "iss": issuer}, sign_with, algorithm="RS256")  # type: ignore[arg-type]


def send(client: TestClient, payload: dict[str, Any], key: str | None = None, sign_with: object = KEY,
         issuer: str = ISSUER) -> httpx.Response:
    body = json.dumps(payload)
    token = sign(payload, sign_with, issuer)
    headers = {"X-Lago-Signature": token, "X-Lago-Signature-Algorithm": "jwt",
               "X-Lago-Unique-Key": key or str(uuid.uuid4()), "Content-Type": "application/json"}
    return client.post("/billing/webhooks/lago", content=body, headers=headers)


def sub_event(kind: str, s: Subscription) -> dict[str, Any]:
    payload = fixture(kind.replace(".", "_"))
    payload["subscription"]["external_id"] = s.lago_external_id
    payload["subscription"]["external_customer_id"] = str(s.workspace_id)
    return payload


def invoice_event(s: Subscription, payment_status: str, *more: Subscription) -> dict[str, Any]:
    """Each call is a new Lago delivery: Lago bumps the invoice's `updated_at` on every status change."""
    payload = fixture("invoice_payment_status_updated")
    invoice = payload["invoice"]
    invoice["payment_status"] = payment_status
    invoice["updated_at"] = (datetime(2026, 11, 1, tzinfo=UTC) + timedelta(seconds=next(_TICKS))).isoformat()
    template = invoice["fees"][0]
    invoice["fees"] = [dict(template, lago_id=str(uuid.uuid4()), external_subscription_id=x.lago_external_id)
                       for x in (s, *more)]
    return payload


def payment_failure_event(s: Subscription) -> dict[str, Any]:
    payload = fixture("invoice_payment_failure")
    payload["payment_provider_invoice_payment_error"]["external_customer_id"] = str(s.workspace_id)
    return payload


def state(db_session: Session, s: Subscription) -> str:
    db_session.refresh(s)
    return s.state


def test_fixtures_are_documented_lago_types() -> None:
    for path in FIXTURES.glob("*.json"):
        payload = json.loads(path.read_text())
        assert payload["webhook_type"] in LAGO_WEBHOOK_TYPES, path.name
        assert payload["object_type"] in payload, path.name


def test_started_activates_and_stores_period_end(client: TestClient, sub: Subscription, db_session: Session) -> None:
    r = send(client, sub_event("subscription.started", sub))
    assert (r.status_code, r.json()) == (200, {"status": "ok"})
    assert state(db_session, sub) == "active"
    assert sub.current_period_end == datetime(2026, 10, 31, 23, 59, 59, tzinfo=UTC)


def test_gated_subscription_lifecycle(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.incomplete", sub))
    assert state(db_session, sub) == "pending"
    send(client, invoice_event(sub, "succeeded"))  # the gating invoice is paid before Lago activates
    assert state(db_session, sub) == "pending"
    send(client, sub_event("subscription.started", sub))
    assert state(db_session, sub) == "active"
    send(client, invoice_event(sub, "failed"))
    assert state(db_session, sub) == "past_due"
    send(client, invoice_event(sub, "succeeded"))
    assert state(db_session, sub) == "active"
    send(client, payment_failure_event(sub))
    assert state(db_session, sub) == "past_due"
    send(client, sub_event("subscription.terminated", sub))
    assert state(db_session, sub) == "canceled"
    assert sub.current_period_end == datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)


def test_declined_first_payment_cancels(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.incomplete", sub))
    send(client, sub_event("subscription.canceled", sub))  # Lago: gated payment failed or timed out
    assert state(db_session, sub) == "canceled"


def test_duplicate_event_is_ignored(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.started", sub), key="evt-1")
    send(client, invoice_event(sub, "failed"), key="evt-2")
    r = send(client, sub_event("subscription.started", sub), key="evt-2")
    assert (r.status_code, r.json()) == (200, {"status": "duplicate"})
    assert send(client, invoice_event(sub, "failed"), key="evt-2").json() == {"status": "duplicate"}
    assert state(db_session, sub) == "past_due"
    event = db_session.get(WebhookEvent, "evt-2")
    assert event is not None
    assert event.type == "invoice.payment_status_updated"
    assert event.processed_at is not None


def test_out_of_order_events_end_active(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.started", sub))
    send(client, sub_event("subscription.incomplete", sub))
    assert state(db_session, sub) == "active"


def test_period_end_never_moves_back(client: TestClient, sub: Subscription, db_session: Session) -> None:
    send(client, sub_event("subscription.terminated", sub))
    send(client, sub_event("subscription.started", sub))  # older delivery, earlier period
    db_session.refresh(sub)
    assert sub.current_period_end == datetime(2026, 11, 30, 23, 59, 59, tzinfo=UTC)


def test_bad_signature_is_400(client: TestClient, sub: Subscription, db_session: Session) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert send(client, sub_event("subscription.started", sub), sign_with=other).status_code == 400
    assert send(client, sub_event("subscription.started", sub), issuer="http://evil").status_code == 400
    assert state(db_session, sub) == "pending"


def test_body_must_match_signed_data(client: TestClient, sub: Subscription, db_session: Session) -> None:
    signed = json.dumps(sub_event("subscription.canceled", sub))
    token = jwt.encode({"data": signed, "iss": ISSUER}, KEY, algorithm="RS256")
    body = json.dumps(sub_event("subscription.started", sub))
    r = client.post("/billing/webhooks/lago", content=body,
                    headers={"X-Lago-Signature": token, "X-Lago-Unique-Key": "k", "Content-Type": "application/json"})
    assert r.status_code == 400
    assert state(db_session, sub) == "pending"


def test_invalid_json_is_400(client: TestClient, sub: Subscription) -> None:
    body = "{not json"
    token = jwt.encode({"data": body, "iss": ISSUER}, KEY, algorithm="RS256")
    r = client.post("/billing/webhooks/lago", content=body,
                    headers={"X-Lago-Signature": token, "X-Lago-Unique-Key": "k", "Content-Type": "application/json"})
    assert r.status_code == 400


def test_missing_unique_key_is_400(client: TestClient, sub: Subscription) -> None:
    body = json.dumps(sub_event("subscription.started", sub))
    token = jwt.encode({"data": body, "iss": ISSUER}, KEY, algorithm="RS256")
    r = client.post("/billing/webhooks/lago", content=body, headers={"X-Lago-Signature": token})
    assert r.status_code == 400


def test_hmac_endpoint_is_400(client: TestClient, sub: Subscription) -> None:
    body = json.dumps(sub_event("subscription.started", sub))
    r = client.post("/billing/webhooks/lago", content=body, headers={
        "X-Lago-Signature": base64.b64encode(b"x" * 32).decode(), "X-Lago-Signature-Algorithm": "hmac",
        "X-Lago-Unique-Key": "k"})
    assert r.status_code == 400


def test_unknown_type_is_400_and_not_stored(client: TestClient, sub: Subscription, db_session: Session) -> None:
    payload = sub_event("subscription.started", sub)
    payload["webhook_type"] = "subscription.activated"
    assert send(client, payload, key="evt-unknown").status_code == 400
    assert db_session.get(WebhookEvent, "evt-unknown") is None
    assert state(db_session, sub) == "pending"


def test_documented_unused_type_is_stored(client: TestClient, sub: Subscription, db_session: Session) -> None:
    payload = fixture("customer_created")
    payload["customer"]["external_id"] = str(sub.workspace_id)
    r = send(client, payload, key="evt-customer")
    assert (r.status_code, r.json()) == (200, {"status": "ok"})
    assert db_session.get(WebhookEvent, "evt-customer") is not None
    assert state(db_session, sub) == "pending"


def test_unknown_subscription_is_acknowledged(client: TestClient, sub: Subscription, db_session: Session) -> None:
    payload = fixture("subscription_started")
    payload["subscription"]["external_id"] = "someone-else"
    assert send(client, payload).status_code == 200
    assert state(db_session, sub) == "pending"


def test_event_before_lago_id_is_saved_still_matches(client: TestClient, sub: Subscription,
                                                     db_session: Session) -> None:
    early = make_sub(db_session, lago_id=False)  # Lago answered the create, we have not saved it yet
    assert send(client, payment_failure_event(early)).status_code == 200
    assert state(db_session, early) == "pending"
    assert send(client, sub_event("subscription.started", early)).status_code == 200
    assert state(db_session, early) == "active"


def test_late_event_for_earlier_attempt_is_ignored(client: TestClient, sub: Subscription,
                                                   db_session: Session) -> None:
    old = sub_event("subscription.canceled", sub)  # attempt 1, canceled; a retry is still in flight
    sub.lago_external_id = sub.lago_subscription_id = f"{sub.workspace_id}:starter:{uuid.uuid4().hex[:8]}"
    sub.state = "active"  # attempt 2 went through
    db_session.flush()
    assert send(client, old).status_code == 200
    assert state(db_session, sub) == "active"


def test_invoice_for_several_subscriptions_updates_each(client: TestClient, db_session: Session) -> None:
    app_of(client).dependency_overrides[get_webhook_verifier] = lambda: WebhookVerifier(PEM, ISSUER)
    first, second = make_sub(db_session, state="active"), make_sub(db_session, state="active")
    untouched = make_sub(db_session, state="active")
    assert send(client, invoice_event(first, "failed", second)).status_code == 200
    assert (state(db_session, first), state(db_session, second), state(db_session, untouched)) == (
        "past_due", "past_due", "active")


def test_replayed_signature_under_new_key_is_duplicate(client: TestClient, sub: Subscription,
                                                       db_session: Session) -> None:
    send(client, sub_event("subscription.started", sub), key="evt-a")
    send(client, invoice_event(sub, "failed"), key="evt-b")
    replay = send(client, sub_event("subscription.started", sub), key="evt-c")  # same JWT, fresh key
    assert (replay.status_code, replay.json()) == (200, {"status": "duplicate"})
    assert state(db_session, sub) == "past_due"
    assert db_session.get(WebhookEvent, "evt-c") is None


def test_concurrent_duplicate_delivery_is_applied_once(connection: Connection, settings: Settings) -> None:
    """Two deliveries of one event on two connections: the second waits for the first, then is a duplicate."""
    engine = engine_for(settings.database_url)
    key = f"evt-{uuid.uuid4()}"
    payload = fixture("customer_created")
    first, second = Session(engine), Session(engine)
    try:
        first.execute(insert(WebhookEvent).values(id=key, type="customer.created", payload=payload))
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(handle_event, second, key, payload, "sig")
            time.sleep(0.3)
            assert not result.done()  # blocked on the first delivery's uncommitted row
            first.commit()
            assert result.result(timeout=10) is False
    finally:
        first.close()
        second.close()
        with engine.begin() as conn:
            conn.execute(delete(WebhookEvent).where(WebhookEvent.id == key))


def _signed_headers(payload: dict[str, Any]) -> dict[str, str]:
    return {"X-Lago-Signature": sign(payload), "X-Lago-Unique-Key": "evt-rejected", "Content-Type": "application/json"}


@pytest.mark.parametrize("case", ["bad_signature", "missing_signature", "missing_key", "hmac", "unknown_type",
                                  "not_an_object"])
def test_every_rejection_is_logged_without_token_or_body(client: TestClient, sub: Subscription, case: str,
                                                         caplog: pytest.LogCaptureFixture) -> None:
    payload: Any = sub_event("subscription.started", sub)
    headers = _signed_headers(payload)
    if case == "bad_signature":
        headers["X-Lago-Signature"] = sign(payload, rsa.generate_private_key(public_exponent=65537, key_size=2048))
    elif case == "missing_signature":
        del headers["X-Lago-Signature"]
    elif case == "missing_key":
        del headers["X-Lago-Unique-Key"]
    elif case == "hmac":
        headers["X-Lago-Signature-Algorithm"] = "hmac"
    elif case == "unknown_type":
        payload["webhook_type"] = "subscription.activated"
        headers = _signed_headers(payload)
    else:
        payload = [payload]
        headers["X-Lago-Signature"] = jwt.encode({"data": json.dumps(payload), "iss": ISSUER}, KEY, algorithm="RS256")
    with caplog.at_level(logging.WARNING, logger="app.billing"):
        r = client.post("/billing/webhooks/lago", content=json.dumps(payload), headers=headers)
    assert r.status_code == 400
    warnings = [rec for rec in caplog.records if rec.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "Rejected Lago webhook" in warnings[0].getMessage()
    if token := headers.get("X-Lago-Signature"):
        assert token not in caplog.text
    assert str(sub.lago_external_id) not in caplog.text  # nothing from the body


@respx.mock
def test_verifier_fetches_public_key_once(client: TestClient, db_session: Session) -> None:
    s = make_sub(db_session)
    lago = LagoClient(LAGO, "k")
    app_of(client).dependency_overrides[get_lago] = lambda: lago
    route = respx.get(f"{LAGO}/api/v1/webhooks/json_public_key").mock(
        return_value=httpx.Response(200, json={"webhook": {"public_key": base64.encodebytes(PEM.encode()).decode()}})
    )
    try:
        assert send(client, sub_event("subscription.started", s)).status_code == 200
        assert send(client, invoice_event(s, "failed")).status_code == 200
    finally:
        _verifier.cache_clear()
    assert route.call_count == 1
    assert state(db_session, s) == "past_due"


@pytest.fixture(autouse=True)
def _no_cached_verifier() -> Iterator[None]:
    yield
    _verifier.cache_clear()
