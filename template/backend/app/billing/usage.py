import uuid

from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.integrations.lago import LagoClient


def record_usage(lago: LagoClient, session: Session, workspace_id: uuid.UUID, metric: str, value: int) -> None:
    """Send a usage event to Lago. Does nothing until the workspace's Lago subscription exists."""
    sub = session.get(Subscription, workspace_id)
    if sub is None or sub.lago_subscription_id is None:
        return
    lago.record_event(str(uuid.uuid4()), sub.lago_subscription_id, metric, {"value": value})
