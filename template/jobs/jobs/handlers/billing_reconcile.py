"""Every 15 minutes: ask Lago for each workspace's subscription and repair our row (spec §6).

Webhooks make changes fast; this keeps them correct. It also finishes a checkout whose owner saved
a card but never came back (Lago sends no webhook for a saved card). It never grants access by
itself beyond what Lago reports: a subscription is `active` in Lago only once its first invoice is paid.
"""

import logging
import os
from typing import Any

import httpx
from sqlalchemy import create_engine

from jobs.db import ScopedDb

log = logging.getLogger(__name__)

# Lago's GET /subscriptions/{external_id} finds only the status it is asked for (default `active`).
LAGO_STATUSES = ("active", "incomplete", "pending", "canceled", "terminated")
LAGO_TO_OURS = {"incomplete": "pending", "pending": "pending", "canceled": "canceled", "terminated": "canceled"}


class LagoUnavailable(Exception):
    pass


def _target(current: str, lago_status: str, latest_payment: str | None = None) -> str:
    """Our state for what Lago reports. For an active Lago subscription the latest invoice decides
    between active and past_due (a missed or late payment webhook leaves the wrong one)."""
    if lago_status == "active":
        if latest_payment == "failed":
            return "past_due"
        if latest_payment == "succeeded":
            return "active"
        return current if current == "past_due" else "active"
    return LAGO_TO_OURS.get(lago_status, current)


class Lago:
    """The few Lago calls reconcile needs (the backend's client is a separate deployable)."""

    def __init__(self, http: httpx.Client) -> None:
        self.http = http

    def _get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._call("GET", path, params=params)

    def _call(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        try:
            response = self.http.request(method, path, **kwargs)
        except httpx.HTTPError as exc:
            raise LagoUnavailable(f"{method} {path}: {exc}") from exc
        if response.status_code >= 500:
            raise LagoUnavailable(f"{method} {path}: HTTP {response.status_code}")
        return response

    @staticmethod
    def _fail(response: httpx.Response) -> LagoUnavailable:
        return LagoUnavailable(f"{response.request.method} {response.request.url.path}: "
                               f"HTTP {response.status_code} {response.text[:200]}")

    def subscription_status(self, external_id: str) -> str | None:
        for status in LAGO_STATUSES:
            response = self._get(f"/api/v1/subscriptions/{external_id}", {"status": status})
            if response.status_code == 404:
                continue
            if response.status_code >= 400:
                raise self._fail(response)
            return str(response.json()["subscription"]["status"])
        return None

    def latest_invoice_payment_status(self, external_customer_id: str) -> str | None:
        response = self._get("/api/v1/invoices", {"external_customer_id": external_customer_id,
                                                  "invoice_type": "subscription", "status": "finalized",
                                                  "per_page": 1})
        if response.status_code >= 400:
            raise self._fail(response)
        invoices = response.json()["invoices"]
        return str(invoices[0]["payment_status"]) if invoices else None

    def has_default_payment_method(self, external_customer_id: str) -> bool:
        response = self._get(f"/api/v1/customers/{external_customer_id}/payment_methods", {"per_page": 100})
        if response.status_code == 404:
            return False
        if response.status_code >= 400:
            raise self._fail(response)
        return any(m.get("is_default") for m in response.json()["payment_methods"])

    def create_gated_subscription(self, external_customer_id: str, plan_code: str, external_id: str) -> None:
        """Same body as the backend's checkout. A repeat create of a still-incomplete subscription
        answers 422 `subscription_incomplete`: it exists, so that is done."""
        body = {"subscription": {
            "external_customer_id": external_customer_id,
            "plan_code": plan_code,
            "external_id": external_id,
            "activation_rules": [{"type": "payment", "timeout_hours": 48}],
        }}
        response = self._call("POST", "/api/v1/subscriptions", json=body)
        if response.status_code == 422:
            details = response.json().get("error_details") or {}
            if "subscription_incomplete" in details.get("subscription", []):
                return
        if response.status_code >= 400:
            raise self._fail(response)


def _store_lago_id(db: ScopedDb, workspace_id: Any, external_id: str) -> bool:
    rows = db.execute(
        "update subscriptions set lago_subscription_id = :external_id, updated_at = CURRENT_TIMESTAMP"
        " where workspace_id = :workspace_id and lago_subscription_id is null and lago_external_id = :external_id"
        " returning workspace_id",
        {"workspace_id": workspace_id, "external_id": external_id},
    )
    return bool(rows)


def _set_state(db: ScopedDb, workspace_id: Any, current: str, target: str) -> bool:
    # Compare-and-set: a webhook that changed the row since we read it wins.
    rows = db.execute(
        "update subscriptions set state = :target, updated_at = CURRENT_TIMESTAMP"
        " where workspace_id = :workspace_id and state = :current returning workspace_id",
        {"workspace_id": workspace_id, "current": current, "target": target},
    )
    return bool(rows)


def _reconcile_one(db: ScopedDb, lago: Lago, workspace_id: Any, sub: dict[str, Any]) -> bool:
    """Returns whether the row changed."""
    customer_id = str(workspace_id)
    state, lago_id = str(sub["state"]), sub["lago_subscription_id"]
    external_id = lago_id or sub["lago_external_id"]
    if external_id is None:
        return False
    status = lago.subscription_status(str(external_id))
    changed = False
    if lago_id is None:
        if status is None:
            # Checkout started, card maybe saved, no Lago subscription yet: finish it (checkout option A).
            if state != "pending" or not lago.has_default_payment_method(customer_id):
                return False
            lago.create_gated_subscription(customer_id, str(sub["plan_code"]), str(external_id))
            return _store_lago_id(db, workspace_id, str(external_id))
        # The create happened but its response was lost: adopt it.
        changed = _store_lago_id(db, workspace_id, str(external_id))
    if status is None:
        return changed
    latest = lago.latest_invoice_payment_status(customer_id) if status == "active" else None
    target = _target(state, status, latest)
    if target != state:
        changed = _set_state(db, workspace_id, state, target) or changed
    return changed


def reconcile(db: ScopedDb, lago: Lago) -> dict[str, int]:
    checked = changed = errors = 0
    for ws in db.unscoped_workspaces():
        rows = db.execute(
            "select plan_code, state, lago_external_id, lago_subscription_id from subscriptions"
            " where workspace_id = :workspace_id",
            {"workspace_id": ws["id"]},
        )
        if not rows:
            continue
        checked += 1
        try:
            changed += _reconcile_one(db, lago, ws["id"], rows[0])
        except (LagoUnavailable, KeyError, ValueError) as exc:  # Lago down, or an answer we cannot read
            log.warning("reconcile %s: %s", ws["id"], repr(exc))
            errors += 1
    return {"checked": checked, "changed": changed, "errors": errors}


def handler(event: dict[str, Any], context: object | None) -> dict[str, int]:
    engine = create_engine(os.environ["DATABASE_URL"])
    http = httpx.Client(base_url=os.environ["LAGO_API_URL"],
                        headers={"Authorization": f"Bearer {os.environ['LAGO_API_KEY']}"}, timeout=15.0)
    try:
        return reconcile(ScopedDb(engine), Lago(http))
    finally:
        http.close()
        engine.dispose()
