import logging
import uuid

import httpx
from sqlalchemy.orm import Session

from app.billing.models import Subscription
from app.errors import DependencyUnavailable
from app.integrations.lago import LagoClient

log = logging.getLogger(__name__)


def record_usage(lago: LagoClient, session: Session, workspace_id: uuid.UUID, metric: str, value: int) -> None:
    """Send a usage event to Lago, best effort.

    Does nothing until the workspace's Lago subscription exists. A Lago failure never breaks the request
    that was already granted: the event is logged and lost. Metered products need an outbox that retries
    with a stable transaction id.
    """
    sub = session.get(Subscription, workspace_id)
    if sub is None or sub.lago_subscription_id is None:
        return
    try:
        lago.record_event(str(uuid.uuid4()), sub.lago_subscription_id, metric, {"value": value})
    except (DependencyUnavailable, httpx.HTTPError) as exc:
        log.warning("Usage event lost: workspace=%s metric=%s error=%s", workspace_id, metric, type(exc).__name__)
