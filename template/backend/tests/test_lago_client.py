import httpx
import pytest
import respx

from app.billing import sync
from app.errors import DependencyRejected
from app.integrations.lago import LagoClient

LAGO = "http://lago.test"
REJECTED = {"status": 422, "error": "Unprocessable Entity", "code": "validation_errors",
            "error_details": {"payment_provider_code": ["value_is_invalid"]}}


def client() -> LagoClient:
    return LagoClient(LAGO, "k")


@respx.mock
def test_customer_create_rejected_is_dependency_rejected_with_lagos_code() -> None:
    respx.post(f"{LAGO}/api/v1/customers").respond(422, json=REJECTED)
    with pytest.raises(DependencyRejected, match="validation_errors"):
        client().create_customer("w1", "Acme", None, "stripe")


@respx.mock
def test_plan_upsert_rejected_is_dependency_rejected() -> None:
    respx.put(f"{LAGO}/api/v1/plans/starter").respond(422, json=REJECTED)
    with pytest.raises(DependencyRejected):
        client().upsert_plan({"plan": {"code": "starter"}})


@respx.mock
def test_plan_upsert_still_creates_on_404() -> None:
    respx.put(f"{LAGO}/api/v1/plans/starter").respond(404, json={"code": "plan_not_found"})
    create = respx.post(f"{LAGO}/api/v1/plans").respond(200, json={})
    client().upsert_plan({"plan": {"code": "starter"}})
    assert create.called


@respx.mock
def test_event_and_public_key_rejections_are_dependency_rejected() -> None:
    respx.post(f"{LAGO}/api/v1/events").respond(422, json=REJECTED)
    respx.get(f"{LAGO}/api/v1/webhooks/json_public_key").respond(401, json={"code": "unauthorized"})
    with pytest.raises(DependencyRejected):
        client().record_event("t1", "s1", "reports_generated", {})
    with pytest.raises(DependencyRejected):
        client().webhook_public_key()


@respx.mock
def test_plan_sync_needs_only_lago_settings(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    for name in ("DATABASE_URL", "STRIPE_SECRET_KEY", "ZITADEL_PROJECT_ID", "FRONTEND_URL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("LAGO_API_URL", LAGO)
    monkeypatch.setenv("LAGO_API_KEY", "k")
    put = respx.put(url__regex=rf"{LAGO}/api/v1/plans/.+").mock(return_value=httpx.Response(200, json={}))
    sync.main()
    assert put.called
    assert "synced plan" in capsys.readouterr().out
