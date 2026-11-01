from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.billing.checkout import start_checkout
from app.billing.plans import Plan, get_plans
from app.db import get_session
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.routes import CurrentWorkspace, current_workspace

router = APIRouter(prefix="/billing")


class CheckoutIn(BaseModel):
    plan_code: str


class CheckoutOut(BaseModel):
    """`checkout_url` null: no redirect needed (card already saved, subscription created or under way)."""

    checkout_url: str | None


@router.get("/plans")
def list_plans(plans: Annotated[dict[str, Plan], Depends(get_plans)]) -> list[dict[str, Any]]:
    return [p.public() for p in plans.values()]


@router.post("/checkout", response_model=CheckoutOut)
def checkout(
    body: CheckoutIn,
    current: Annotated[CurrentWorkspace, Depends(current_workspace)],
    session: Annotated[Session, Depends(get_session)],
    lago: Annotated[LagoClient, Depends(get_lago)],
    plans: Annotated[dict[str, Plan], Depends(get_plans)],
) -> CheckoutOut:
    if current.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can change the plan")
    plan = plans.get(body.plan_code)
    if plan is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Unknown plan {body.plan_code!r}")
    return CheckoutOut(checkout_url=start_checkout(session, current.workspace, plan, lago))
