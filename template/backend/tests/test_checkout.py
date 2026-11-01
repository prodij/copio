import json

import httpx
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from tests.auth_helpers import AuthHeaders
from tests.fakes import LAGO, fake_lago_billing

STARTER = {"plan_code": "starter"}


def subscription(db_session: Session) -> Subscription:
    return db_session.scalars(select(Subscription).execution_options(populate_existing=True)).one()


@respx.mock
def test_without_card_returns_setup_url_and_records_checkout(client: TestClient, owner_headers: dict[str, str],
                                                             db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=False)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 200
    assert r.json() == {"checkout_url": "https://checkout.stripe.test/s"}
    assert lago["sub"].call_count == 0
    assert lago["methods"].calls.last.request.url.params["per_page"] == "100"
    sub = subscription(db_session)
    assert (sub.plan_code, sub.state, sub.lago_subscription_id) == ("starter", "pending", None)


@respx.mock
def test_with_card_creates_gated_subscription(client: TestClient, owner_headers: dict[str, str],
                                              owner_workspace: str, db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 200
    assert r.json() == {"checkout_url": None}
    assert lago["url"].call_count == 0
    body = json.loads(lago["sub"].calls.last.request.content)["subscription"]
    assert body == {"external_customer_id": owner_workspace, "plan_code": "starter",
                    "external_id": f"{owner_workspace}:starter",
                    "activation_rules": [{"type": "payment", "timeout_hours": 48}]}
    sub = subscription(db_session)
    assert (sub.state, sub.lago_subscription_id) == ("pending", f"{owner_workspace}:starter")


@respx.mock
def test_return_trip_finishes_checkout_once(client: TestClient, owner_headers: dict[str, str],
                                            db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=False)
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).json()["checkout_url"]
    lago["methods"].mock(return_value=httpx.Response(200, json={  # the card was saved on Stripe's page
        "payment_methods": [{"lago_id": "pm-1", "is_default": True}], "meta": {}}))
    for _ in range(2):
        assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).json() == {"checkout_url": None}
    assert lago["sub"].call_count == 1
    assert subscription(db_session).state == "pending"


@respx.mock
def test_lost_create_response_counts_as_done(client: TestClient, owner_headers: dict[str, str],
                                             owner_workspace: str, db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    lago["sub"].mock(return_value=httpx.Response(422, json={
        "status": 422, "error": "Unprocessable Entity", "code": "validation_errors",
        "error_details": {"subscription": ["subscription_incomplete"]}}))
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.json() == {"checkout_url": None}
    assert subscription(db_session).lago_subscription_id == f"{owner_workspace}:starter"


@respx.mock
def test_canceled_workspace_can_check_out_again(client: TestClient, owner_headers: dict[str, str],
                                                db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    sub = subscription(db_session)
    sub.state = "canceled"
    db_session.commit()
    client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert lago["sub"].call_count == 2
    assert subscription(db_session).state == "pending"


@respx.mock
def test_lago_rejection_is_a_clear_502(client: TestClient, owner_headers: dict[str, str]) -> None:
    lago = fake_lago_billing(respx.mock, card=False)
    lago["url"].mock(return_value=httpx.Response(422, json={
        "status": 422, "error": "Unprocessable Entity", "code": "validation_errors",
        "error_details": {"provider_payment_methods": ["no_payment_methods_to_setup_available"]}}))
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 502
    assert r.json()["detail"].startswith("Lago rejected the request: validation_errors")
    assert "no_payment_methods_to_setup_available" in r.json()["detail"]


@respx.mock
def test_lago_down_is_503(client: TestClient, owner_headers: dict[str, str]) -> None:
    respx.get(url__regex=rf"{LAGO}/api/v1/customers/.+/payment_methods").mock(return_value=httpx.Response(502))
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert (r.status_code, r.json()) == (503, {"detail": "Lago is unavailable"})


@respx.mock
def test_unsynced_stripe_customer_is_503_not_a_dead_checkout(client: TestClient,
                                                              owner_headers: dict[str, str]) -> None:
    lago = fake_lago_billing(respx.mock, card=False, synced=False)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert (r.status_code, r.json()) == (503, {"detail": "Stripe customer is unavailable"})
    assert lago["url"].call_count == 0


def test_unknown_plan_is_422(client: TestClient, owner_headers: dict[str, str]) -> None:
    r = client.post("/billing/checkout", json={"plan_code": "gold"}, headers=owner_headers)
    assert r.status_code == 422


def test_member_cannot_checkout(client: TestClient, owner_workspace: str, auth: AuthHeaders) -> None:
    member = auth("user-2", {owner_workspace: "member"})
    assert client.post("/billing/checkout", json=STARTER, headers=member).status_code == 403


def test_checkout_needs_sign_in(client: TestClient) -> None:
    assert client.post("/billing/checkout", json=STARTER).status_code == 401


def test_list_plans(client: TestClient) -> None:
    plans = client.get("/billing/plans").json()
    assert plans[0]["code"] == "starter"
    assert set(plans[0]) == {"code", "name", "amount_cents", "currency", "interval", "features"}
