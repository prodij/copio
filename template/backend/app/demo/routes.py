from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.access.deps import require_feature
from app.billing.usage import record_usage
from app.db import get_session
from app.integrations import get_lago
from app.integrations.lago import LagoClient
from app.workspaces.routes import CurrentWorkspace

router = APIRouter(prefix="/demo")


@router.get("/premium-report")
def premium_report(
    current: Annotated[CurrentWorkspace, Depends(require_feature("premium_report"))],
    session: Annotated[Session, Depends(get_session)],
    lago: Annotated[LagoClient, Depends(get_lago)],
) -> dict[str, str]:
    record_usage(lago, session, current.workspace.id, "reports_generated", 1)
    return {"title": "Premium report", "generated_for": current.workspace.name}
