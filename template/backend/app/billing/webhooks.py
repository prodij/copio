"""Lago webhooks (lago-api v1.55.0): verify the JWT signature, store each delivery once, apply it.

Lago signs every delivery with `X-Lago-Signature`: an RS256 JWT whose `data` claim is the JSON
body and whose `iss` is Lago's LAGO_API_URL (endpoint signature_algo `jwt`, Lago's default).
`X-Lago-Unique-Key` is Lago's webhook id, the same on every retry of one delivery.
"""

import json
import logging
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.billing.models import Subscription, WebhookEvent
from app.billing.states import next_state
from app.config import Settings, get_settings
from app.integrations import get_lago
from app.integrations.lago import LagoClient

log = logging.getLogger(__name__)

# Every webhook type Lago v1.55.0 can send (lago-api config/webhook_event_types.yml).
LAGO_WEBHOOK_TYPES = frozenset({
    "alert.triggered",
    "billable_metric.created", "billable_metric.updated", "billable_metric.deleted",
    "customer.created", "customer.updated", "customer.accounting_provider_created",
    "customer.accounting_provider_error", "customer.crm_provider_created", "customer.crm_provider_error",
    "customer.payment_provider_created", "customer.payment_provider_error", "customer.checkout_url_generated",
    "customer.tax_provider_error", "customer.vies_check",
    "credit_note.created", "credit_note.generated", "credit_note.provider_refund_failure",
    "dunning_campaign.finished",
    "event.error", "events.errors",
    "feature.created", "feature.updated", "feature.deleted",
    "fee.created", "fee.tax_provider_error",
    "invoice.created", "invoice.one_off_created", "invoice.paid_credit_added", "invoice.generated",
    "invoice.drafted", "invoice.ready_to_finalize", "invoice.voided", "invoice.deleted",
    "invoice.payment_dispute_lost", "invoice.payment_status_updated", "invoice.payment_overdue",
    "invoice.payment_failure", "invoice.resynced",
    "integration.provider_error",
    "order.created", "order.executed",
    "order_form.created", "order_form.signed", "order_form.expired", "order_form.voided",
    "payment.succeeded", "payment.requires_action",
    "payment_provider.error",
    "payment_receipt.created", "payment_receipt.generated",
    "payment_request.created", "payment_request.payment_failure", "payment_request.payment_status_updated",
    "plan.created", "plan.updated", "plan.deleted",
    "quote.created", "quote.approved", "quote.voided",
    "subscription.canceled", "subscription.incomplete", "subscription.terminated", "subscription.started",
    "subscription.updated", "subscription.termination_alert", "subscription.trial_ended",
    "subscription.usage_threshold_reached",
    "wallet.created", "wallet.depleted_ongoing_balance", "wallet.terminated", "wallet.updated",
    "wallet_transaction.created", "wallet_transaction.updated", "wallet_transaction.payment_failure",
})

# The types that can change a subscription's state (see app.billing.states).
STATE_WEBHOOK_TYPES = frozenset({
    "subscription.incomplete", "subscription.started", "subscription.canceled", "subscription.terminated",
    "invoice.payment_status_updated", "invoice.payment_failure",
})


class BadSignature(Exception):
    pass


class UnknownWebhookType(Exception):
    pass


class WebhookVerifier:
    def __init__(self, public_key_pem: str, issuer: str) -> None:
        self.key = public_key_pem
        self.issuer = issuer

    def verify(self, raw_body: bytes, signature: str) -> dict[str, Any]:
        try:
            claims = jwt.decode(signature, self.key, algorithms=["RS256"], issuer=self.issuer,
                                options={"require": ["iss"], "verify_aud": False})
            body = json.loads(raw_body)
            if json.loads(claims["data"]) != body:
                raise BadSignature("body does not match signed data")
        except (jwt.PyJWTError, KeyError, TypeError, ValueError) as exc:
            raise BadSignature(str(exc)) from exc
        if not isinstance(body, dict):
            raise BadSignature("body is not a JSON object")
        return body


@lru_cache
def _verifier(lago: LagoClient, issuer: str) -> WebhookVerifier:
    return WebhookVerifier(lago.webhook_public_key(), issuer)


def get_webhook_verifier(
    settings: Annotated[Settings, Depends(get_settings)],
    lago: Annotated[LagoClient, Depends(get_lago)],
) -> WebhookVerifier:
    """Fetches Lago's public key on first use, then reuses it. A Lago outage is not cached (503, Lago retries)."""
    return _verifier(lago, settings.lago_webhook_issuer)


def _dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _subscriptions(session: Session, payload: dict[str, Any]) -> list[Subscription]:
    """The subscriptions a delivery is about, locked. Rows still without a Lago id never match by external id."""
    object_type = payload.get("object_type")
    obj = _dict(payload.get(str(object_type)))
    if object_type == "subscription":
        condition = Subscription.lago_subscription_id == str(obj.get("external_id"))
    elif object_type == "invoice":
        # Lago's invoice webhooks carry fees, not subscriptions; each fee names its subscription.
        fees = obj.get("fees")
        fees = fees if isinstance(fees, list) else []
        ids = {str(f["external_subscription_id"]) for f in fees
               if isinstance(f, dict) and f.get("external_subscription_id")}
        condition = Subscription.lago_subscription_id.in_(sorted(ids))
    elif object_type == "payment_provider_invoice_payment_error":
        # invoice.payment_failure names only the customer, whose external id is our workspace id.
        try:
            workspace_id = uuid.UUID(str(obj.get("external_customer_id")))
        except ValueError:
            return []
        condition = Subscription.workspace_id == workspace_id
    else:
        return []
    return list(session.scalars(
        select(Subscription).where(condition).order_by(Subscription.workspace_id).with_for_update()
    ))


def _period_end(payload: dict[str, Any]) -> datetime | None:
    if payload.get("object_type") != "subscription":
        return None
    value = _dict(payload.get("subscription")).get("current_billing_period_ending_at")
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed is not None and parsed.tzinfo is None else parsed


def handle_event(session: Session, event_id: str, payload: dict[str, Any]) -> bool:
    """Applies one verified delivery at most once. False if `event_id` was already processed."""
    webhook_type = payload.get("webhook_type")
    if webhook_type not in LAGO_WEBHOOK_TYPES:
        log.warning("Rejected Lago webhook %s: unknown type %r", event_id, webhook_type)
        raise UnknownWebhookType(str(webhook_type))
    webhook_type = str(webhook_type)
    inserted = session.execute(
        insert(WebhookEvent).values(id=event_id, type=webhook_type, payload=payload)
        .on_conflict_do_nothing(index_elements=["id"]).returning(WebhookEvent.id)
    ).scalar_one_or_none()
    if inserted is None:
        log.info("Ignored duplicate Lago webhook %s (%s)", event_id, webhook_type)
        return False
    if webhook_type in STATE_WEBHOOK_TYPES or webhook_type.startswith("subscription."):
        payment_status = _dict(payload.get("invoice")).get("payment_status")
        period_end = _period_end(payload)
        for sub in _subscriptions(session, payload):
            before = sub.state
            sub.state = next_state(sub.state, webhook_type, payment_status)
            if period_end is not None and (sub.current_period_end is None or period_end > sub.current_period_end):
                sub.current_period_end = period_end
            log.info("Lago webhook %s (%s): workspace %s %s -> %s",
                     event_id, webhook_type, sub.workspace_id, before, sub.state)
    else:
        log.info("Stored Lago webhook %s (%s): not used for subscription state", event_id, webhook_type)
    event = session.get(WebhookEvent, event_id)
    if event is not None:
        event.processed_at = datetime.now(UTC)
    session.commit()
    return True
