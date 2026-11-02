import itertools
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.access.rules import decide
from app.billing.models import Subscription
from app.billing.plans import Plan, load_plans
from app.billing.usage import record_usage
from app.config import Settings, get_settings
from app.integrations.lago import LagoClient
from app.workspaces.models import Workspace
from tests.fakes import LAGO

PLANS = {
    "starter": Plan("starter", "Starter", 100, "USD", "month", {"premium_report": True, "seats": 5}),
    "free": Plan("free", "Free", 0, "USD", "month", {"premium_report": False}),
}
STATES = [None, "pending", "active", "past_due", "canceled"]
PLAN_CODES = [None, "starter", "free"]
FEATURES = ["premium_report", "seats", "not_a_feature"]


def expected(state: str | None, plan: str | None, feature: str) -> bool:
    if state not in {"active", "past_due"} or plan is None:
        return False
    return bool(PLANS[plan].features.get(feature, False))


@pytest.mark.parametrize(("state", "plan", "feature"), list(itertools.product(STATES, PLAN_CODES, FEATURES)))
def test_every_combination(state: str | None, plan: str | None, feature: str) -> None:
    assert decide(state, plan, PLANS, feature).allowed is expected(state, plan, feature)


def test_unknown_plan_denies() -> None:
    decision = decide("active", "gold", PLANS, "premium_report")
    assert decision.allowed is False
    assert decision.reason == "unknown plan 'gold'"


def test_reasons_are_human() -> None:
    assert decide(None, None, PLANS, "premium_report").reason == "no subscription"
    assert decide("pending", "starter", PLANS, "premium_report").reason == "subscription is pending"
    assert decide("active", "free", PLANS, "premium_report").reason == "plan 'free' does not include premium_report"


def _subscribe(db_session: Session, state: str, *, plan_code: str = "starter", lago_id: str | None = "ext-1",
               period_end: datetime | None = None) -> None:
    ws = db_session.query(Workspace).one()
    db_session.add(Subscription(workspace_id=ws.id, plan_code=plan_code, state=state, lago_external_id=lago_id,
                                lago_subscription_id=lago_id, current_period_end=period_end))
    db_session.flush()


def test_premium_report_needs_active_plan(client: TestClient, owner_headers: dict[str, str],
                                          db_session: Session) -> None:
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert r.status_code == 402
    assert r.json() == {"detail": "no subscription"}
    _subscribe(db_session, "active")
    with respx.mock:
        events = respx.post(f"{LAGO}/api/v1/events").mock(return_value=httpx.Response(200, json={}))
        r = client.get("/demo/premium-report", headers=owner_headers)
    assert r.status_code == 200
    assert r.json() == {"title": "Premium report", "generated_for": "Acme"}
    sent = json.loads(events.calls.last.request.content)["event"]
    assert (sent["external_subscription_id"], sent["code"], sent["properties"]) == (
        "ext-1", "reports_generated", {"value": 1})


def test_pending_checkout_is_denied_and_reported_honestly(client: TestClient, owner_headers: dict[str, str],
                                                          db_session: Session) -> None:
    _subscribe(db_session, "pending", lago_id=None)
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert (r.status_code, r.json()) == (402, {"detail": "subscription is pending"})
    assert client.get("/me/access", headers=owner_headers).json() == {
        "billing_configured": True, "mock_payment": False, "plan_code": "starter", "state": "pending", "current_period_end": None, "features": {}}


def test_unknown_plan_is_402_not_a_crash(client: TestClient, owner_headers: dict[str, str],
                                         db_session: Session) -> None:
    _subscribe(db_session, "active", plan_code="gold")
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert (r.status_code, r.json()) == (402, {"detail": "unknown plan 'gold'"})
    assert client.get("/me/access", headers=owner_headers).json() == {
        "billing_configured": True, "mock_payment": False, "plan_code": "gold", "state": "active", "current_period_end": None, "features": {}}


def test_me_access(client: TestClient, owner_headers: dict[str, str], db_session: Session) -> None:
    assert client.get("/me/access", headers=owner_headers).json() == {
        "billing_configured": True, "mock_payment": False, "plan_code": None, "state": None, "current_period_end": None, "features": {}}
    _subscribe(db_session, "past_due", period_end=datetime(2026, 12, 1, tzinfo=UTC))
    assert client.get("/me/access", headers=owner_headers).json() == {
        "billing_configured": True, "mock_payment": False, "plan_code": "starter", "state": "past_due", "current_period_end": "2026-12-01T00:00:00Z",
        "features": load_plans()["starter"].features}  # the product's plans.yaml, whatever it grants


def test_me_access_canceled_has_no_features(client: TestClient, owner_headers: dict[str, str],
                                            db_session: Session) -> None:
    _subscribe(db_session, "canceled")
    body = client.get("/me/access", headers=owner_headers).json()
    assert (body["state"], body["features"]) == ("canceled", {})


def test_plans_endpoint_shape(client: TestClient, owner_headers: dict[str, str]) -> None:
    plans = client.get("/billing/plans", headers=owner_headers).json()
    assert {p["code"] for p in plans} == set(load_plans())
    assert all(set(p) == {"code", "name", "amount_cents", "currency", "interval", "features"} for p in plans)


@respx.mock
def test_record_usage_skips_workspaces_without_a_lago_subscription(db_session: Session,
                                                                   owner_workspace: str) -> None:
    events = respx.post(f"{LAGO}/api/v1/events").mock(return_value=httpx.Response(200, json={}))
    lago = LagoClient(LAGO, "k")
    workspace_id = uuid.UUID(owner_workspace)
    record_usage(lago, db_session, workspace_id, "reports_generated", 1)  # no subscription row
    _subscribe(db_session, "pending", lago_id=None)
    record_usage(lago, db_session, workspace_id, "reports_generated", 1)  # pending, not in Lago yet
    assert events.call_count == 0


@pytest.mark.parametrize("outage", [
    httpx.Response(503, json={}),
    httpx.ConnectError("down"),
    httpx.Response(422, json={"code": "validation_errors"}),
], ids=["503", "connect-error", "4xx"])
def test_premium_report_survives_lago_outage(client: TestClient, owner_headers: dict[str, str],
                                             db_session: Session, caplog: pytest.LogCaptureFixture,
                                             outage: httpx.Response | Exception) -> None:
    _subscribe(db_session, "active")
    with respx.mock:
        route = respx.post(f"{LAGO}/api/v1/events")
        route.mock(side_effect=outage) if isinstance(outage, Exception) else route.mock(return_value=outage)
        with caplog.at_level(logging.WARNING, logger="app.billing.usage"):
            r = client.get("/demo/premium-report", headers=owner_headers)
    assert r.status_code == 200
    assert any("Usage event lost" in m and "reports_generated" in m for m in caplog.messages)


def test_without_stripe_access_says_so_and_still_denies(client: TestClient, owner_headers: dict[str, str],
                                                        settings: Settings) -> None:
    without_key = settings.model_copy(update={"stripe_secret_key": ""})
    cast(FastAPI, client.app).dependency_overrides[get_settings] = lambda: without_key
    assert client.get("/me/access", headers=owner_headers).json() == {
        "billing_configured": False, "mock_payment": False, "plan_code": None, "state": None, "current_period_end": None, "features": {}}
    r = client.get("/demo/premium-report", headers=owner_headers)
    assert (r.status_code, r.json()) == (402, {"detail": "no subscription"})
