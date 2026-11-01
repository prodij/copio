from dataclasses import dataclass
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import require_principal
from app.auth.principal import Principal
from app.config import Settings, get_settings
from app.db import get_session
from app.integrations import get_lago, get_zitadel
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
from app.workspaces.models import Workspace
from app.workspaces.service import create_workspace

router = APIRouter()


class CreateWorkspace(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()


class WorkspaceOut(BaseModel):
    id: str
    name: str
    status: str


class MeWorkspace(BaseModel):
    id: str
    name: str
    role: str


class MeOut(BaseModel):
    user_id: str
    email: str | None
    workspace: MeWorkspace | None


@dataclass(frozen=True)
class CurrentWorkspace:
    workspace: Workspace
    role: str


def _find(session: Session, principal: Principal, wanted: str | None) -> CurrentWorkspace | None:
    if not principal.roles_by_org:
        return None
    rows = session.scalars(
        select(Workspace).where(Workspace.zitadel_org_id.in_(list(principal.roles_by_org)), Workspace.status == "ready")
    ).all()
    if wanted:
        rows = [w for w in rows if str(w.id) == wanted]
    if not rows:
        return None
    ws = sorted(rows, key=lambda w: w.created_at)[0]
    return CurrentWorkspace(ws, principal.roles_by_org[ws.zitadel_org_id or ""])


def current_workspace(
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
    x_workspace_id: Annotated[str | None, Header()] = None,
) -> CurrentWorkspace:
    found = _find(session, principal, x_workspace_id)
    if found is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No workspace for this user")
    return found


@router.post("/workspaces", status_code=201, response_model=WorkspaceOut)
def post_workspace(
    body: CreateWorkspace,
    response: Response,
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
    zitadel: Annotated[ZitadelClient, Depends(get_zitadel)],
    lago: Annotated[LagoClient, Depends(get_lago)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkspaceOut:
    ws, created = create_workspace(session, principal, body.name, zitadel, lago, settings)
    if not created:
        response.status_code = 200
    return WorkspaceOut(id=str(ws.id), name=ws.name, status=ws.status)


@router.get("/me", response_model=MeOut)
def get_me(
    principal: Annotated[Principal, Depends(require_principal)],
    session: Annotated[Session, Depends(get_session)],
) -> MeOut:
    found = _find(session, principal, None)
    ws = MeWorkspace(id=str(found.workspace.id), name=found.workspace.name, role=found.role) if found else None
    return MeOut(user_id=principal.user_id, email=principal.email, workspace=ws)


@router.get("/me/workspace", response_model=MeWorkspace)
def get_my_workspace(current: Annotated[CurrentWorkspace, Depends(current_workspace)]) -> MeWorkspace:
    return MeWorkspace(id=str(current.workspace.id), name=current.workspace.name, role=current.role)
