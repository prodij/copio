from dataclasses import dataclass

from app.billing.plans import Plan
from app.billing.states import GRANTING


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


def decide(state: str | None, plan_code: str | None, plans: dict[str, Plan], feature: str) -> Decision:
    """The one access rule. Everything that grants or reports access goes through here."""
    if state is None or plan_code is None:
        return Decision(False, "no subscription")
    if state not in GRANTING:
        return Decision(False, f"subscription is {state}")
    plan = plans.get(plan_code)
    if plan is None:
        return Decision(False, f"unknown plan {plan_code!r}")
    if not plan.features.get(feature):
        return Decision(False, f"plan {plan_code!r} does not include {feature}")
    return Decision(True, "ok")
