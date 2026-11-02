import pathlib

import pytest

from app.billing.plans import PlanFileError, load_plans


def write(tmp_path: pathlib.Path, text: str) -> pathlib.Path:
    p = tmp_path / "plans.yaml"
    p.write_text(text)
    return p


def test_shipped_plans_load() -> None:
    plans = load_plans()
    assert "starter" in plans
    assert plans["starter"].features["premium_report"] is True


def test_to_lago_shape() -> None:
    body = load_plans()["starter"].to_lago()
    assert body["plan"]["code"] == "starter"
    assert body["plan"]["pay_in_advance"] is True
    assert body["plan"]["interval"] in {"monthly", "yearly"}
    assert body["plan"]["amount_currency"] == "USD"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: week, features: {}}]", "interval"),
        ("plans: [{code: a, name: A, amount_cents: -1, currency: USD, interval: month, features: {}}]", "amount"),
        ("plans: [{code: a, name: A, amount_cents: 1.5, currency: USD, interval: month, features: {}}]", "amount"),
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: month, features: {}},"
         " {code: a, name: B, amount_cents: 1, currency: USD, interval: month, features: {}}]", "duplicate"),
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: month, features: {x: maybe}}]", "feature"),
        ("plans: [{code: a, name: A, amount_cents: 1, currency: USD, interval: month, features: {x: -1}}]", "feature"),
        ("plans: [{code: a, name: A, amount_cents: 1, interval: month}]", "missing currency"),
    ],
)
def test_bad_plan_files_are_rejected(tmp_path: pathlib.Path, text: str, message: str) -> None:
    with pytest.raises(PlanFileError, match=message):
        load_plans(write(tmp_path, text))
