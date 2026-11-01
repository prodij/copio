import httpx
import respx

ZITADEL = "http://zitadel.test"
LAGO = "http://lago.test"


def fake_zitadel(mock: respx.MockRouter, org_id: str = "org-new") -> dict[str, respx.Route]:
    return {
        "org": mock.post(f"{ZITADEL}/v2/organizations").mock(
            return_value=httpx.Response(200, json={"organizationId": org_id})
        ),
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
