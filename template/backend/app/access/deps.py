from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.access.rules import decide
from app.billing.models import Subscription
from app.billing.plans import Plan, get_plans
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace


def require_feature(feature: str) -> Callable[..., CurrentWorkspace]:
    """The only access check: 402 with the reason when the workspace's subscription does not grant `feature`."""

    def dependency(
        current: Annotated[CurrentWorkspace, Depends(current_workspace)],
        session: Annotated[Session, Depends(get_session)],
        plans: Annotated[dict[str, Plan], Depends(get_plans)],
    ) -> CurrentWorkspace:
        sub = session.get(Subscription, current.workspace.id)
        decision = decide(sub.state if sub else None, sub.plan_code if sub else None, plans, feature)
        if not decision.allowed:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, decision.reason)
        return current

    return dependency
