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
        "user": mock.get(url__regex=rf"{ZITADEL}/v2/users/[^/]+$").mock(
            return_value=httpx.Response(200, json={"user": {"userId": "user-1", "human": {
                "email": {"email": "owner@example.com", "isVerified": True}}}})
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


def lago_customer(*, provider: bool = True, synced: bool = True) -> httpx.Response:
    """GET /customers/{id}, shaped like lago-api v1.55.0's serializer: no `provider_customer_id` key without a provider."""
    if not provider:
        return httpx.Response(200, json={"customer": {"billing_configuration": {
            "payment_provider": None, "payment_provider_code": None}}})
    return httpx.Response(200, json={"customer": {"billing_configuration": {
        "payment_provider": "stripe", "payment_provider_code": "stripe",
        "provider_customer_id": "cus_x" if synced else None}}})


def fake_lago_billing(mock: respx.MockRouter, *, card: bool, synced: bool = True,
                      provider: bool = True) -> dict[str, respx.Route]:
    """Lago's checkout-side endpoints for one customer, shaped like lago-api v1.55.0's serializers."""
    methods = [{"lago_id": "pm-1", "is_default": True, "provider_method_id": "pm_x"}] if card else []
    return {
        "customer": mock.get(url__regex=rf"{LAGO}/api/v1/customers/[^/]+$").mock(
            return_value=lago_customer(provider=provider, synced=synced)
        ),
        "upsert": mock.post(f"{LAGO}/api/v1/customers").mock(
            return_value=httpx.Response(200, json={"customer": {"lago_id": "lago-cust-1"}})
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
