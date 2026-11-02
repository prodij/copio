import base64
from typing import Any

import httpx

from app.errors import DependencyRejected, DependencyUnavailable


class LagoClient:
    def __init__(self, api_url: str, api_key: str, http: httpx.Client | None = None) -> None:
        self.http = http or httpx.Client(
            base_url=api_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=15.0
        )

    def _call(self, method: str, path: str, body: dict[str, Any] | None = None,
              params: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = self.http.request(method, path, json=body, params=params)
        except httpx.HTTPError as exc:
            raise DependencyUnavailable("Lago") from exc
        if response.status_code >= 500:
            raise DependencyUnavailable("Lago")
        return response

    @staticmethod
    def _stripe_billing(provider_code: str) -> dict[str, Any]:
        return {
            "payment_provider": "stripe",
            "payment_provider_code": provider_code,
            "sync_with_provider": True,
            "provider_payment_methods": ["card"],
        }

    def create_customer(self, external_id: str, name: str, email: str | None, provider_code: str | None) -> str:
        """Lago upserts customers on external_id, so repeating this call never duplicates.

        `provider_code` None (no Stripe configured): no billing configuration; checkout attaches it later.
        """
        customer: dict[str, Any] = {"external_id": external_id, "name": name, "email": email}
        if provider_code is not None:
            customer["billing_configuration"] = self._stripe_billing(provider_code)
        response = self._call("POST", "/api/v1/customers", {"customer": customer})
        self._check(response)
        return str(response.json()["customer"]["lago_id"])

    def _attach_stripe(self, external_id: str, provider_code: str) -> None:
        """Give an existing customer the Stripe provider, for a workspace created before Stripe was set up.

        Lago's upsert (v1.55.0 Customers::UpsertFromApiService) sets only the fields it receives, so
        name and email stay, and queues the job that creates the Stripe customer. Each repeat while
        that job has not finished queues another, so call this only when no provider is set yet.
        """
        body = {"customer": {"external_id": external_id, "billing_configuration": self._stripe_billing(provider_code)}}
        self._check(self._call("POST", "/api/v1/customers", body))

    def upsert_plan(self, body: dict[str, Any]) -> None:
        code = body["plan"]["code"]
        response = self._call("PUT", f"/api/v1/plans/{code}", body)
        if response.status_code == 404:
            response = self._call("POST", "/api/v1/plans", body)
        self._check(response)

    @staticmethod
    def _errors(response: httpx.Response) -> dict[str, Any]:
        """Lago's 4xx body: {"status", "error", "code", "error_details": {field: [codes]}}."""
        try:
            body = response.json()
        except ValueError:
            return {}
        return body if isinstance(body, dict) else {}

    def _check(self, response: httpx.Response) -> None:
        if response.status_code >= 400:
            body = self._errors(response)
            reason = body.get("code") or f"HTTP {response.status_code}"
            if details := body.get("error_details"):
                reason = f"{reason} {details}"
            raise DependencyRejected("Lago", str(reason))

    def create_subscription(self, external_customer_id: str, plan_code: str, external_id: str) -> None:
        """Creates a payment-gated subscription: Lago keeps it `incomplete` until the first invoice is paid.

        Lago only accepts the payment rule when the customer already has a default payment
        method (else 422 `no_default_payment_method`). A repeat create for a subscription that
        is still `incomplete` answers 422 `subscription_incomplete`: that means it exists, so done.
        """
        body = {"subscription": {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            "external_id": external_id,
            "activation_rules": [{"type": "payment", "timeout_hours": 48}],
        }}
        response = self._call("POST", "/api/v1/subscriptions", body)
        details = self._errors(response).get("error_details") or {}
        if response.status_code == 422 and "subscription_incomplete" in details.get("subscription", []):
            return
        self._check(response)

    def has_default_payment_method(self, external_customer_id: str) -> bool:
        response = self._call("GET", f"/api/v1/customers/{external_customer_id}/payment_methods",
                              params={"per_page": 100})
        self._check(response)
        return any(m.get("is_default") for m in response.json()["payment_methods"])

    def checkout_url(self, external_customer_id: str, provider_code: str) -> str:
        """URL of a Stripe Checkout page in setup mode: it saves a card, it charges nothing.

        Lago creates the Stripe customer in a background job. A checkout started before that
        job ran has no Stripe customer, and Lago would never learn about the card, so refuse
        (a customer from before Stripe was set up gets its provider now, which starts that job).
        """
        customer = self._call("GET", f"/api/v1/customers/{external_customer_id}")
        self._check(customer)
        billing = customer.json()["customer"].get("billing_configuration", {})
        if not billing.get("payment_provider"):
            self._attach_stripe(external_customer_id, provider_code)
            raise DependencyUnavailable("Stripe customer")
        if not billing.get("provider_customer_id"):
            raise DependencyUnavailable("Stripe customer")
        response = self._call("POST", f"/api/v1/customers/{external_customer_id}/checkout_url")
        self._check(response)
        return str(response.json()["customer"]["checkout_url"])

    def record_event(self, transaction_id: str, external_subscription_id: str, code: str,
                     properties: dict[str, Any]) -> None:
        body = {"event": {"transaction_id": transaction_id, "external_subscription_id": external_subscription_id,
                          "code": code, "properties": properties}}
        self._check(self._call("POST", "/api/v1/events", body))

    def webhook_public_key(self) -> str:
        response = self._call("GET", "/api/v1/webhooks/json_public_key")
        self._check(response)
        return base64.b64decode(response.json()["webhook"]["public_key"]).decode()
