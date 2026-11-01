"""The only place subscription state transitions are defined (spec §6).

A payment-gated Lago subscription reports `subscription.incomplete` when created and
`subscription.started` once its first invoice is paid, so `started` is "invoice paid".
Lago cancels a gated subscription whose first payment fails or times out (`subscription.canceled`).
"""

GRANTING = frozenset({"active", "past_due"})


def next_state(current: str, webhook_type: str, payment_status: str | None = None) -> str:
    if webhook_type in {"subscription.canceled", "subscription.terminated"}:
        return "canceled"
    if webhook_type == "subscription.started":
        return current if current == "canceled" else "active"
    if webhook_type == "invoice.payment_failure":
        return "past_due" if current == "active" else current
    if webhook_type == "invoice.payment_status_updated":
        if payment_status == "failed" and current == "active":
            return "past_due"
        if payment_status == "succeeded" and current == "past_due":
            return "active"
    return current
