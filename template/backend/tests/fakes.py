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
