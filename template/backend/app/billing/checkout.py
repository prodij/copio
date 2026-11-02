import secrets

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.billing.plans import Plan
from app.integrations.lago import LagoClient
from app.workspaces.models import Workspace


class PlanChangeNotSupported(Exception):
    """The workspace already has a Lago subscription on another plan."""


def new_external_id(ws: Workspace, plan: Plan) -> str:
    """A fresh Lago external id per checkout attempt: late webhooks for an earlier attempt match nothing."""
    return f"{ws.id}:{plan.code}:{secrets.token_hex(4)}"


def _record_checkout(session: Session, ws: Workspace, plan: Plan) -> Subscription:
    """Note that a checkout started (plan chosen, no Lago subscription yet), so reconcile can finish it.

    The attempt's external id is saved here, before Lago is asked to create anything, so a create
    whose response was lost is repeated with the same id (and Lago answers "already exists").
    """
    session.execute(
        insert(Subscription)
        .values(workspace_id=ws.id, plan_code=plan.code, state="pending",
                lago_external_id=new_external_id(ws, plan), lago_subscription_id=None)
        .on_conflict_do_nothing(index_elements=[Subscription.workspace_id])
    )
    session.commit()
    sub = session.scalars(
        select(Subscription).where(Subscription.workspace_id == ws.id).execution_options(populate_existing=True)
    ).one()
    if sub.state == "canceled":
        sub.plan_code, sub.state, sub.lago_subscription_id = plan.code, "pending", None
        sub.lago_external_id = new_external_id(ws, plan)
        session.commit()
    elif sub.lago_subscription_id is None and (sub.plan_code != plan.code or sub.lago_external_id is None):
        sub.plan_code, sub.lago_external_id = plan.code, new_external_id(ws, plan)
        session.commit()
    elif sub.lago_subscription_id is not None and sub.plan_code != plan.code:
        raise PlanChangeNotSupported
    return sub


def start_checkout(session: Session, ws: Workspace, plan: Plan, lago: LagoClient, provider_code: str) -> str | None:
    """Returns the Stripe setup URL to send the owner to, or None when no redirect is needed.

    Lago's payment-gated subscription needs a saved card first, and Lago sends no webhook when
    a card is saved. So: without a card → setup URL (call again after the return trip); with a
    card → create the gated subscription once. Neither grants access: the invoice-paid webhook does.
    """
    sub = _record_checkout(session, ws, plan)
    if sub.lago_subscription_id is not None:
        return None
    customer_id = str(ws.id)
    if not lago.has_default_payment_method(customer_id):
        return lago.checkout_url(customer_id, provider_code)
    external_id = str(sub.lago_external_id)
    lago.create_subscription(customer_id, plan.code, external_id)
    sub.lago_subscription_id = external_id
    session.commit()
    return None
