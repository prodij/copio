import json

import httpx
import respx

ZITADEL = "http://zitadel.test"
LAGO = "http://lago.test"


def _echo_org_id(request: httpx.Request) -> httpx.Response:
    """Real Zitadel answers with the organizationId it was asked to use (the workspace id)."""
    return httpx.Response(200, json={"organizationId": json.loads(request.content)["organizationId"]})


def fake_zitadel(mock: respx.MockRouter) -> dict[str, respx.Route]:
    return {
        "org": mock.post(f"{ZITADEL}/v2/organizations").mock(side_effect=_echo_org_id),
        "grant": mock.post(f"{ZITADEL}/management/v1/projects/proj-1/grants").mock(
            return_value=httpx.Response(200, json={"grantId": "grant-1"})
        ),
        "user_grant": mock.post(url__regex=rf"{ZITADEL}/management/v1/users/.+/grants").mock(
            return_value=httpx.Response(200, json={"userGrantId": "ug-1"})
        ),
    }


def fake_lago(mock: respx.MockRouter) -> dict[str, respx.Route]:
    return {
        "customer": mock.post(f"{LAGO}/api/v1/customers").mock(
            return_value=httpx.Response(200, json={"customer": {"lago_id": "lago-cust-1"}})
        ),
    }


def fake_lago_billing(mock: respx.MockRouter, *, card: bool, synced: bool = True) -> dict[str, respx.Route]:
    """Lago's checkout-side endpoints for one customer, shaped like lago-api v1.55.0's serializers."""
    methods = [{"lago_id": "pm-1", "is_default": True, "provider_method_id": "pm_x"}] if card else []
    provider_customer_id = "cus_x" if synced else None
    return {
        "customer": mock.get(url__regex=rf"{LAGO}/api/v1/customers/[^/]+$").mock(
            return_value=httpx.Response(200, json={"customer": {"billing_configuration": {
                "payment_provider": "stripe", "provider_customer_id": provider_customer_id}}})
        ),
        "methods": mock.get(url__regex=rf"{LAGO}/api/v1/customers/.+/payment_methods").mock(
            return_value=httpx.Response(200, json={"payment_methods": methods, "meta": {"current_page": 1}})
        ),
        "url": mock.post(url__regex=rf"{LAGO}/api/v1/customers/.+/checkout_url").mock(
            return_value=httpx.Response(200, json={"customer": {"checkout_url": "https://checkout.stripe.test/s"}})
        ),
        "sub": mock.post(f"{LAGO}/api/v1/subscriptions").mock(
            return_value=httpx.Response(200, json={"subscription": {"external_id": "x", "status": "pending"}})
        ),
    }
