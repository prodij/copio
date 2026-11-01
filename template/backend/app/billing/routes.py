import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.billing.checkout import start_checkout
from app.billing.plans import Plan, get_plans
from app.billing.webhooks import (
    BadSignature,
    UnknownWebhookType,
    WebhookVerifier,
    get_webhook_verifier,
    handle_event,
)
from app.db import get_session
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.routes import CurrentWorkspace, current_workspace

log = logging.getLogger(__name__)
router = APIRouter(prefix="/billing")


class CheckoutIn(BaseModel):
    plan_code: str


class CheckoutOut(BaseModel):
    """`checkout_url` null: no redirect needed (card already saved, subscription created or under way)."""

    checkout_url: str | None


class PlanOut(BaseModel):
    code: str
    name: str
    amount_cents: int
    currency: str
    interval: str
    features: dict[str, bool | int]


@router.get("/plans", response_model=list[PlanOut])
def list_plans(plans: Annotated[dict[str, Plan], Depends(get_plans)]) -> list[PlanOut]:
    return [PlanOut(**p.public()) for p in plans.values()]


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


def _reject(event_id: str | None, reason: str) -> HTTPException:
    """Spec §9: a rejected delivery is a 400 and is logged, with the reason only (never the token or body)."""
    log.warning("Rejected Lago webhook %s: %s", (event_id or "-")[:128], reason)
    return HTTPException(status.HTTP_400_BAD_REQUEST, reason)


def _process_webhook(session: Session, verifier: WebhookVerifier, raw_body: bytes, signature: str,
                     event_id: str) -> bool:
    try:
        payload = verifier.verify(raw_body, signature)
    except BadSignature as exc:
        raise _reject(event_id, f"bad signature: {exc}") from exc
    try:
        return handle_event(session, event_id, payload, signature)
    except UnknownWebhookType as exc:
        raise _reject(event_id, str(exc)) from exc


@router.post("/webhooks/lago")
async def lago_webhook(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    verifier: Annotated[WebhookVerifier, Depends(get_webhook_verifier)],
    x_lago_signature: Annotated[str | None, Header()] = None,
    x_lago_unique_key: Annotated[str | None, Header()] = None,
    x_lago_signature_algorithm: Annotated[str | None, Header()] = None,
) -> dict[str, str]:
    """Async only to read the raw body (the signature covers it); verifying and the DB work run in a thread."""
    if not x_lago_signature:
        raise _reject(x_lago_unique_key, "missing X-Lago-Signature")
    if not x_lago_unique_key or len(x_lago_unique_key) > 128:
        raise _reject(None, "missing or oversized X-Lago-Unique-Key")
    if x_lago_signature_algorithm not in (None, "jwt"):
        raise _reject(x_lago_unique_key, "signature algorithm is not jwt (endpoint must use signature_algo jwt)")
    raw_body = await request.body()
    processed = await run_in_threadpool(
        _process_webhook, session, verifier, raw_body, x_lago_signature, x_lago_unique_key
    )
    return {"status": "ok" if processed else "duplicate"}
