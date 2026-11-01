from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.access.rules import decide
from app.billing.models import Subscription
from app.billing.plans import Plan, get_plans
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter()


class AccessOut(BaseModel):
    """`state` is the subscription's own state (including `pending`); `features` holds only what it grants now."""

    plan_code: str | None
    state: str | None
    current_period_end: datetime | None
    features: dict[str, bool | int]


@router.get("/me/access", response_model=AccessOut)
def my_access(
    current: Annotated[CurrentWorkspace, Depends(current_workspace)],
    session: Annotated[Session, Depends(get_session)],
    plans: Annotated[dict[str, Plan], Depends(get_plans)],
) -> AccessOut:
    sub = session.get(Subscription, current.workspace.id)
    if sub is None:
        return AccessOut(plan_code=None, state=None, current_period_end=None, features={})
    plan = plans.get(sub.plan_code)
    names = plan.features if plan else {}
    features = {name: names[name] for name in names if decide(sub.state, sub.plan_code, plans, name).allowed}
    return AccessOut(plan_code=sub.plan_code, state=sub.state, current_period_end=sub.current_period_end,
                     features=features)
