import base64
from typing import Any

import httpx

from app.errors import DependencyUnavailable


class LagoClient:
    def __init__(self, api_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15.0
        )

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = self.http.request(method, path, json=body)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable("Lago") from exc
        if response.status_code >= 500:
            raise DependencyUnavailable("Lago")
        return response

    def create_customer(self, external_id: str, name: str, email: str | None, provider_code: str) -> str:
        """Lago upserts customers on external_id, so repeating this call never duplicates."""
        body = {"customer": {
            "external_id": external_id,
            "name": name,
            "email": email,
            "billing_configuration": {
                "payment_provider": "stripe",
                "payment_provider_code": provider_code,
                "sync_with_provider": True,
                "provider_payment_methods": ["card"],
            },
        }}
        response = self._call("POST", "/api/v1/customers", body)
        response.raise_for_status()
        return str(response.json()["customer"]["lago_id"])

    def upsert_plan(self, body: dict[str, Any]) -> None:
        code = body["plan"]["code"]
        response = self._call("PUT", f"/api/v1/plans/{code}", body)
        if response.status_code == 404:
            response = self._call("POST", "/api/v1/plans", body)
        response.raise_for_status()

    def create_subscription(self, external_customer_id: str, plan_code: str, external_id: str) -> dict[str, Any]:
        body = {"subscription": {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            "external_id": external_id,
            "activation_rules": [{"type": "payment", "timeout_hours": 48}],
        }}
        response = self._call("POST", "/api/v1/subscriptions", body)
        response.raise_for_status()
        result: dict[str, Any] = response.json()["subscription"]
        return result

    def checkout_url(self, external_customer_id: str) -> str:
        response = self._call("POST", f"/api/v1/customers/{external_customer_id}/checkout_url")
        response.raise_for_status()
        return str(response.json()["customer"]["checkout_url"])

    def get_subscription(self, external_id: str) -> dict[str, Any] | None:
        """Lago's GET returns only an `active` subscription unless `?status=` says otherwise."""
        response = self._call("GET", f"/api/v1/subscriptions/{external_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        result: dict[str, Any] = response.json()["subscription"]
        return result

    def record_event(self, transaction_id: str, external_subscription_id: str, code: str,
                     properties: dict[str, Any]) -> None:
        body = {"event": {"transaction_id": transaction_id, "external_subscription_id": external_subscription_id,
                          "code": code, "properties": properties}}
        self._call("POST", "/api/v1/events", body).raise_for_status()

    def webhook_public_key(self) -> str:
        response = self._call("GET", "/api/v1/webhooks/json_public_key")
        response.raise_for_status()
        return base64.b64decode(response.json()["webhook"]["public_key"]).decode()
