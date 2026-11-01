import base64
import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
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
from sqlalchemy.orm import Session

from app.billing.models import Subscription, WebhookEvent
from app.billing.webhooks import (
    LAGO_WEBHOOK_TYPES,
    WebhookVerifier,
    _verifier,
    get_webhook_verifier,
)
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.models import Workspace
from tests.fakes import LAGO

ISSUER = "http://lago.test"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PEM = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
FIXTURES = Path(__file__).parent / "fixtures" / "lago"


def fixture(name: str) -> dict[str, Any]:
    """A webhook body shaped like lago-api v1.55.0 sends it (see tests/fixtures/lago)."""
    result: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())
    return result


def app_of(client: TestClient) -> FastAPI:
    return cast(FastAPI, client.app)


def make_sub(db_session: Session, lago_id: bool = True) -> Subscription:
    ws = Workspace(name="Acme", owner_user_id=f"u-{uuid.uuid4()}", status="ready")
    db_session.add(ws)
    db_session.flush()
    s = Subscription(workspace_id=ws.id, plan_code="starter", state="pending",
                     lago_subscription_id=f"{ws.id}:starter" if lago_id else None)
    db_session.add(s)
    db_session.flush()
    return s


@pytest.fixture
def sub(db_session: Session, client: TestClient) -> Subscription:
    app_of(client).dependency_overrides[get_webhook_verifier] = lambda: WebhookVerifier(PEM, ISSUER)
    return make_sub(db_session)


def send(client: TestClient, payload: dict[str, Any], key: str | None = None, sign_with: object = KEY,
         issuer: str = ISSUER) -> httpx.Response:
    body = json.dumps(payload)
    token = jwt.encode({"data": body, "iss": issuer}, sign_with, algorithm="RS256")  # type: ignore[arg-type]
    headers = {"X-Lago-Signature": token, "X-Lago-Signature-Algorithm": "jwt",
               "X-Lago-Unique-Key": key or str(uuid.uuid4()), "Content-Type": "application/json"}
    return client.post("/billing/webhooks/lago", content=body, headers=headers)


def sub_event(kind: str, s: Subscription) -> dict[str, Any]:
    payload = fixture(kind.replace(".", "_"))
    payload["subscription"]["external_id"] = s.lago_subscription_id or f"{s.workspace_id}:{s.plan_code}"
    payload["subscription"]["external_customer_id"] = str(s.workspace_id)
    return payload


def invoice_event(s: Subscription, payment_status: str) -> dict[str, Any]:
    payload = fixture("invoice_payment_status_updated")
    payload["invoice"]["payment_status"] = payment_status
    for fee in payload["invoice"]["fees"]:
        fee["external_subscription_id"] = s.lago_subscription_id
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


def test_row_without_lago_subscription_is_untouched(client: TestClient, sub: Subscription,
                                                    db_session: Session) -> None:
    started = make_sub(db_session, lago_id=False)  # checkout started, no Lago subscription yet
    assert send(client, sub_event("subscription.started", started)).status_code == 200
    assert send(client, payment_failure_event(started)).status_code == 200
    assert state(db_session, started) == "pending"
    assert started.lago_subscription_id is None


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
