import pytest

from app.billing.states import next_state


@pytest.mark.parametrize(
    ("current", "webhook", "payment", "expected"),
    [
        ("pending", "subscription.incomplete", None, "pending"),
        ("active", "subscription.incomplete", None, "active"),
        ("pending", "subscription.started", None, "active"),
        ("past_due", "subscription.started", None, "active"),
        ("canceled", "subscription.started", None, "canceled"),
        ("active", "subscription.canceled", None, "canceled"),
        ("pending", "subscription.canceled", None, "canceled"),
        ("pending", "subscription.terminated", None, "canceled"),
        ("past_due", "subscription.terminated", None, "canceled"),
        ("active", "invoice.payment_failure", None, "past_due"),
        ("pending", "invoice.payment_failure", None, "pending"),
        ("active", "invoice.payment_status_updated", "failed", "past_due"),
        ("pending", "invoice.payment_status_updated", "failed", "pending"),
        ("past_due", "invoice.payment_status_updated", "succeeded", "active"),
        ("pending", "invoice.payment_status_updated", "succeeded", "pending"),
        ("active", "invoice.payment_status_updated", "pending", "active"),
        ("active", "subscription.updated", None, "active"),
        ("active", "customer.created", None, "active"),
    ],
)
def test_transitions(current: str, webhook: str, payment: str | None, expected: str) -> None:
    assert next_state(current, webhook, payment) == expected
