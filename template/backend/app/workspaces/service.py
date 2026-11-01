from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.principal import Principal
from app.config import Settings
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
from app.workspaces.models import Workspace


def org_name(ws: Workspace) -> str:
    """Zitadel org names are unique per instance, so two customers may both say "Acme"."""
    return f"{ws.name} ({str(ws.id)[:8]})"


def create_workspace(session: Session, principal: Principal, name: str, zitadel: ZitadelClient,
                     lago: LagoClient, settings: Settings) -> tuple[Workspace, bool]:
    """Returns (workspace, created_now).

    Progress is committed after every external step, so a retry resumes from the last
    finished one. Each external call is also safe to repeat: the org ID is the workspace ID,
    Zitadel's 409s count as done, and Lago upserts customers on external_id.
    """
    ws = session.scalars(select(Workspace).where(Workspace.owner_user_id == principal.user_id)).one_or_none()
    if ws is not None and ws.status == "ready":
        return ws, False
    if ws is None:
        ws = Workspace(name=name, owner_user_id=principal.user_id)
        session.add(ws)
        session.commit()
    if ws.zitadel_org_id is None:
        ws.zitadel_org_id = zitadel.create_org(org_name(ws), org_id=str(ws.id))
        session.commit()
    if ws.zitadel_grant_id is None:
        ws.zitadel_grant_id = zitadel.grant_project(ws.zitadel_org_id)
        session.commit()
    # Not recorded separately: repeating it is harmless (Zitadel answers 409, treated as done).
    zitadel.add_user_role(principal.user_id, ws.zitadel_org_id, ws.zitadel_grant_id, "owner")
    if ws.lago_customer_id is None:
        ws.lago_customer_id = lago.create_customer(str(ws.id), ws.name, principal.email,
                                                   settings.lago_stripe_provider_code)
        session.commit()
    ws.status = "ready"
    session.commit()
    return ws, True
