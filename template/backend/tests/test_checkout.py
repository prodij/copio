import json
import re
from typing import cast

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.billing.plans import Plan, get_plans
from app.config import Settings, get_settings
from tests.auth_helpers import AuthHeaders
from tests.fakes import LAGO, fake_lago_billing, lago_customer

STARTER = {"plan_code": "starter"}


def attempt_id(workspace_id: str, plan_code: str = "starter") -> re.Pattern[str]:
    return re.compile(rf"{workspace_id}:{plan_code}:[0-9a-f]{{8}}")


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
    external_id = body.pop("external_id")
    assert attempt_id(owner_workspace).fullmatch(external_id)
    assert body == {"external_customer_id": owner_workspace, "plan_code": "starter",
                    "activation_rules": [{"type": "payment", "timeout_hours": 48}]}
    sub = subscription(db_session)
    assert (sub.state, sub.lago_external_id, sub.lago_subscription_id) == ("pending", external_id, external_id)


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
    sub = subscription(db_session)
    assert attempt_id(owner_workspace).fullmatch(str(sub.lago_subscription_id))
    assert sub.lago_subscription_id == sub.lago_external_id


@respx.mock
def test_attempt_id_is_saved_before_create_and_reused_on_retry(client: TestClient, owner_headers: dict[str, str],
                                                               db_session: Session) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    lago["sub"].mock(side_effect=[httpx.Response(502), httpx.Response(200, json={"subscription": {}})])
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).status_code == 503
    saved = subscription(db_session)
    assert saved.lago_external_id is not None
    assert saved.lago_subscription_id is None
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).json() == {"checkout_url": None}
    sent = [json.loads(c.request.content)["subscription"]["external_id"] for c in lago["sub"].calls]
    assert sent == [saved.lago_external_id] * 2


@respx.mock
def test_plan_switch_before_create_gets_new_attempt_id(client: TestClient, owner_headers: dict[str, str],
                                                       owner_workspace: str, db_session: Session) -> None:
    fake_lago_billing(respx.mock, card=False)
    plans = {code: Plan(code, code.title(), 1900, "USD", "month") for code in ("starter", "pro")}
    cast(FastAPI, client.app).dependency_overrides[get_plans] = lambda: plans
    client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    first = subscription(db_session).lago_external_id
    client.post("/billing/checkout", json={"plan_code": "pro"}, headers=owner_headers)
    sub = subscription(db_session)
    assert sub.plan_code == "pro"
    assert attempt_id(owner_workspace, "pro").fullmatch(str(sub.lago_external_id))
    assert sub.lago_external_id != first


@respx.mock
def test_plan_change_after_lago_subscription_is_409_and_keeps_the_plan(
    client: TestClient, owner_headers: dict[str, str], db_session: Session,
) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    plans = {code: Plan(code, code.title(), 1900, "USD", "month") for code in ("starter", "pro")}
    cast(FastAPI, client.app).dependency_overrides[get_plans] = lambda: plans
    client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    before = subscription(db_session).lago_subscription_id
    assert before is not None

    r = client.post("/billing/checkout", json={"plan_code": "pro"}, headers=owner_headers)

    assert r.status_code == 409
    assert r.json() == {"detail": "plan change not supported yet"}
    sub = subscription(db_session)
    assert (sub.plan_code, sub.lago_subscription_id) == ("starter", before)
    assert lago["sub"].call_count == 1
    # The same plan again stays the harmless repeat the return trip relies on.
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).json() == {"checkout_url": None}


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
    first, second = (json.loads(c.request.content)["subscription"]["external_id"] for c in lago["sub"].calls)
    assert first != second  # a late webhook for the canceled attempt cannot touch the new one
    restarted = subscription(db_session)
    assert (restarted.state, restarted.lago_external_id, restarted.lago_subscription_id) == ("pending", second, second)


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
    assert lago["upsert"].call_count == 0  # it has its provider; a repeat would queue a second Stripe customer


@respx.mock
def test_customer_from_before_the_key_gets_the_provider_at_checkout(client: TestClient, owner_headers: dict[str, str],
                                                                    owner_workspace: str) -> None:
    lago = fake_lago_billing(respx.mock, card=False, provider=False)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    # Lago now creates the Stripe customer in its background job: the same 503 the Plans page retries.
    assert (r.status_code, r.json()) == (503, {"detail": "Stripe customer is unavailable"})
    assert lago["url"].call_count == 0
    assert json.loads(lago["upsert"].calls.last.request.content) == {"customer": {
        "external_id": owner_workspace,  # only this and the provider: Lago keeps the name and email
        "billing_configuration": {"payment_provider": "stripe", "payment_provider_code": "stripe",
                                  "sync_with_provider": True, "provider_payment_methods": ["card"]}}}

    lago["customer"].mock(return_value=lago_customer(synced=False))  # the job is still running
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).status_code == 503
    assert lago["upsert"].call_count == 1

    lago["customer"].mock(return_value=lago_customer())  # the job finished
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.json() == {"checkout_url": "https://checkout.stripe.test/s"}
    assert lago["upsert"].call_count == 1


@respx.mock
def test_attaching_a_provider_lago_does_not_have_is_a_clear_502(client: TestClient,
                                                                owner_headers: dict[str, str]) -> None:
    lago = fake_lago_billing(respx.mock, card=False, provider=False)
    lago["upsert"].mock(return_value=httpx.Response(422, json={
        "status": 422, "error": "Unprocessable Entity", "code": "payment_provider_not_found"}))
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 502
    assert "payment_provider_not_found" in r.json()["detail"]


@pytest.fixture
def no_stripe(client: TestClient, settings: Settings) -> None:
    without_key = settings.model_copy(update={"stripe_secret_key": ""})
    cast(FastAPI, client.app).dependency_overrides[get_settings] = lambda: without_key


@respx.mock
def test_checkout_without_stripe_is_a_clear_501_and_writes_nothing(
    client: TestClient, owner_headers: dict[str, str], no_stripe: None, db_session: Session,
) -> None:
    lago = fake_lago_billing(respx.mock, card=False)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 501
    assert r.json()["detail"].startswith("Billing isn't set up")
    assert "STRIPE_SECRET_KEY" in r.json()["detail"]
    assert db_session.scalars(select(Subscription)).first() is None
    assert not any(route.called for route in lago.values())


@respx.mock
def test_checkout_works_once_the_key_is_added(client: TestClient, owner_headers: dict[str, str], no_stripe: None,
                                              settings: Settings) -> None:
    fake_lago_billing(respx.mock, card=False)
    assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).status_code == 501
    cast(FastAPI, client.app).dependency_overrides[get_settings] = lambda: settings
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.json() == {"checkout_url": "https://checkout.stripe.test/s"}


@pytest.fixture
def mock_payment(client: TestClient, settings: Settings) -> None:
    mock = settings.model_copy(update={"stripe_secret_key": "", "billing_mode": "mock", "app_env": "local"})
    cast(FastAPI, client.app).dependency_overrides[get_settings] = lambda: mock


@respx.mock
def test_mock_payment_creates_a_subscription_with_no_payment_rule_and_grants_nothing(
    client: TestClient, owner_headers: dict[str, str], owner_workspace: str, mock_payment: None, db_session: Session,
) -> None:
    lago = fake_lago_billing(respx.mock, card=False, provider=False)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert (r.status_code, r.json()) == (200, {"checkout_url": None})
    body = json.loads(lago["sub"].calls.last.request.content)["subscription"]
    external_id = body.pop("external_id")
    assert body == {"external_customer_id": owner_workspace, "plan_code": "starter"}
    sub = subscription(db_session)
    assert (sub.state, sub.lago_subscription_id) == ("pending", external_id)
    # No Stripe anywhere: no provider attached, no card looked up, no setup URL.
    assert not any(lago[name].called for name in ("upsert", "methods", "url"))
    # Back in the browser, access is still off.
    assert client.get("/demo/premium-report", headers=owner_headers).status_code == 402
    access = client.get("/me/access", headers=owner_headers).json()
    assert (access["mock_payment"], access["state"], access["features"]) == (True, "pending", {})


@respx.mock
def test_mock_payment_creates_the_subscription_once(client: TestClient, owner_headers: dict[str, str],
                                                    mock_payment: None) -> None:
    lago = fake_lago_billing(respx.mock, card=False, provider=False)
    for _ in range(2):
        assert client.post("/billing/checkout", json=STARTER, headers=owner_headers).json() == {"checkout_url": None}
    assert lago["sub"].call_count == 1


@respx.mock
def test_mock_payment_is_refused_for_a_customer_with_a_payment_provider(
    client: TestClient, owner_headers: dict[str, str], mock_payment: None, db_session: Session,
) -> None:
    lago = fake_lago_billing(respx.mock, card=False, provider=True)
    r = client.post("/billing/checkout", json=STARTER, headers=owner_headers)
    assert r.status_code == 409 and "Mock payment is refused" in r.json()["detail"]
    assert lago["sub"].call_count == 0 and db_session.scalars(select(Subscription)).first() is None


@respx.mock
def test_mock_payment_keeps_the_owner_check_and_the_plan_check(
    client: TestClient, owner_workspace: str, auth: AuthHeaders, owner_headers: dict[str, str], mock_payment: None,
) -> None:
    member = auth("user-2", {owner_workspace: "member"})
    assert client.post("/billing/checkout", json=STARTER, headers=member).status_code == 403
    r = client.post("/billing/checkout", json={"plan_code": "nope"}, headers=owner_headers)
    assert r.status_code == 422


@respx.mock
@pytest.mark.parametrize("request_args", [
    {"params": {"billing_mode": "mock", "mock": "true", "mock_payment": "1"}},
    {"headers": {"X-Billing-Mode": "mock", "Billing-Mode": "mock", "X-Mock-Payment": "1"}},
    {"body": {"billing_mode": "mock", "mock_payment": True}},
])
def test_no_request_can_turn_on_mock_payment(client: TestClient, owner_headers: dict[str, str], db_session: Session,
                                             no_stripe: None, request_args: dict[str, dict[str, object]]) -> None:
    lago = fake_lago_billing(respx.mock, card=False)
    r = client.post("/billing/checkout", json=STARTER | request_args.get("body", {}),
                    params=request_args.get("params"),
                    headers=owner_headers | request_args.get("headers", {}))
    assert r.status_code == 501
    assert lago["sub"].call_count == 0 and db_session.scalars(select(Subscription)).first() is None
    assert client.get("/me/access", headers=owner_headers).json()["mock_payment"] is False


@respx.mock
def test_with_a_key_the_request_cannot_drop_the_payment_rule(client: TestClient, owner_headers: dict[str, str]) -> None:
    lago = fake_lago_billing(respx.mock, card=True)
    r = client.post("/billing/checkout", json=STARTER | {"billing_mode": "mock"}, params={"billing_mode": "mock"},
                    headers=owner_headers | {"X-Billing-Mode": "mock"})
    assert r.json() == {"checkout_url": None}
    assert json.loads(lago["sub"].calls.last.request.content)["subscription"]["activation_rules"] == [
        {"type": "payment", "timeout_hours": 48}]


def test_without_stripe_a_member_is_still_403_and_a_bad_plan_still_422(
    client: TestClient, owner_workspace: str, auth: AuthHeaders, owner_headers: dict[str, str], no_stripe: None,
) -> None:
    member = auth("user-2", {owner_workspace: "member"})
    assert client.post("/billing/checkout", json=STARTER, headers=member).status_code == 403
    assert client.post("/billing/checkout", json={"plan_code": "gold"}, headers=owner_headers).status_code == 422


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
    starter = next(p for p in plans if p["code"] == "starter")
    assert set(starter) == {"code", "name", "amount_cents", "currency", "interval", "features"}
