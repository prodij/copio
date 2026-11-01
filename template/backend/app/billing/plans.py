from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PLANS_PATH = Path(__file__).with_name("plans.yaml")
LAGO_INTERVAL = {"month": "monthly", "year": "yearly"}
REQUIRED = ("code", "name", "amount_cents", "currency", "interval")


class PlanFileError(ValueError):
    pass


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    amount_cents: int
    currency: str
    interval: str
    features: dict[str, bool | int] = field(default_factory=dict)

    def to_lago(self) -> dict[str, Any]:
        return {"plan": {
            "code": self.code,
            "name": self.name,
            "amount_cents": self.amount_cents,
            "amount_currency": self.currency,
            "interval": LAGO_INTERVAL[self.interval],
            "pay_in_advance": True,
            "charges": [],
        }}

    def public(self) -> dict[str, Any]:
        return {"code": self.code, "name": self.name, "amount_cents": self.amount_cents,
                "currency": self.currency, "interval": self.interval, "features": dict(self.features)}


def _plan(item: dict[str, Any]) -> Plan:
    missing = [key for key in REQUIRED if key not in item]
    if missing:
        raise PlanFileError(f"plan {item.get('code')!r}: missing {', '.join(missing)}")
    code = str(item["code"])
    if item["interval"] not in LAGO_INTERVAL:
        raise PlanFileError(f"plan {code!r}: interval must be month or year")
    amount = item["amount_cents"]
    if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
        raise PlanFileError(f"plan {code!r}: amount_cents must be a whole number >= 0")
    features = item.get("features") or {}
    for name, value in features.items():
        if not (isinstance(value, bool) or (isinstance(value, int) and value >= 0)):
            raise PlanFileError(f"plan {code!r}: feature {name!r} must be true/false or a whole number")
    return Plan(code, str(item["name"]), amount, str(item["currency"]), str(item["interval"]), dict(features))


def load_plans(path: Path = PLANS_PATH) -> dict[str, Plan]:
    raw = yaml.safe_load(path.read_text()) or {}
    plans: dict[str, Plan] = {}
    for item in raw.get("plans", []):
        plan = _plan(item)
        if plan.code in plans:
            raise PlanFileError(f"duplicate plan code {plan.code!r}")
        plans[plan.code] = plan
    return plans


@lru_cache
def get_plans() -> dict[str, Plan]:
    return load_plans()
