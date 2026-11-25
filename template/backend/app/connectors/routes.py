"""Connection management: list, create, pause, resume, reconnect, disconnect, and per-dataset schedules.

Every route is scoped to the caller's workspace (`current_workspace`); a connection id from another
workspace is a 404, never a 403, so ids don't leak. Reads are open to any member; changes need the
workspace owner, like billing. Every change calls `app.audit.record` in the same transaction.

Credentials are write-only: they arrive as `SecretStr`, are sealed by the vault before they touch the
database, and no response, audit detail, log line or validation error carries them (validation errors
on this router drop the submitted input; see `_RedactingRoute`).
"""

from __future__ import annotations

import uuid
import zoneinfo
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.auth.deps import require_principal
from app.auth.principal import Principal
from app.connectors.models import Connection, Credential, SyncSchedule
from app.connectors.vault import Secret, Vault, VaultMisconfigured, get_vault
from app.db import get_session
from app.workspaces.routes import CurrentWorkspace, current_workspace

# Providers a connection may be created for. The template ships only the synthetic test provider; a
# product adds its real adapters here.
PROVIDERS = ("synthetic",)
Provider = Literal["synthetic"]


class _RedactingRoute(APIRoute):
    """422s without the submitted values: FastAPI's default echoes `input`, which could be a token."""

    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        handler = super().get_route_handler()

        async def redacting(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError as exc:
                errors = [{"type": e.get("type"), "loc": list(e.get("loc", ())), "msg": e.get("msg")}
                          for e in exc.errors()]
                return JSONResponse({"detail": errors}, status_code=422)

        return redacting


router = APIRouter(prefix="/connections", tags=["connections"], route_class=_RedactingRoute)


# ---- shapes


class CredentialsIn(BaseModel):
    access_token: SecretStr = Field(min_length=1, max_length=8192)
    expires_at: datetime | None = None
    extra: dict[str, SecretStr] = Field(default_factory=dict, max_length=20)

    def secret(self) -> Secret:
        return Secret(access_token=self.access_token.get_secret_value(),
                      extra={k: v.get_secret_value() for k, v in self.extra.items()})


class CreateConnection(BaseModel):
    provider: Provider
    account_ref: str = Field(min_length=1, max_length=255)
    display_name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    config: dict[str, str | int | bool] = Field(default_factory=dict, max_length=50)
    credentials: CredentialsIn


class ReconnectIn(BaseModel):
    credentials: CredentialsIn


class ScheduleIn(BaseModel):
    kind: Literal["incremental", "backfill", "report"] = "incremental"
    cron: str = Field(min_length=9, max_length=64)
    timezone: str = "UTC"
    jitter_s: int = Field(0, ge=0, le=3600)
    overlap: Literal["skip", "queue_one"] = "skip"
    catchup_window_s: int = Field(3600, ge=0, le=7 * 86400)
    lookback_s: int = Field(0, ge=0, le=30 * 86400)
    paused: bool = False

    @field_validator("cron")
    @classmethod
    def five_fields(cls, value: str) -> str:
        if len(value.split()) != 5:
            raise ValueError("cron must have five fields (minute hour day month weekday)")
        return " ".join(value.split())

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, value: str) -> str:
        try:
            zoneinfo.ZoneInfo(value)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("unknown timezone") from exc
        return value


class ScheduleOut(BaseModel):
    dataset: str
    kind: str
    cron: str
    timezone: str
    jitter_s: int
    overlap: str
    catchup_window_s: int
    lookback_s: int
    paused: bool
    next_due_at: datetime | None


class ConnectionOut(BaseModel):
    """Never carries a credential: only whether one is stored and when it expires."""

    id: str
    provider: str
    account_ref: str
    display_name: str
    state: str
    state_reason: str | None
    scopes: list[str]
    created_at: datetime
    updated_at: datetime
    has_credential: bool
    credential_expires_at: datetime | None
    schedules: list[ScheduleOut]


# ---- helpers

DATASET = Annotated[str, Path(pattern=r"^[a-z0-9_]{1,64}$")]


def _vault() -> Vault:
    try:
        return get_vault()
    except VaultMisconfigured as exc:  # the message names variables, never values
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"connector vault: {exc}") from None


def _owner(current: CurrentWorkspace) -> None:
    if current.role != "owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can change connections")


def _get(session: Session, current: CurrentWorkspace, connection_id: uuid.UUID, *,
         for_update: bool = False) -> Connection:
    query = select(Connection).where(Connection.id == connection_id,
                                     Connection.workspace_id == current.workspace.id)
    conn = session.scalars(query.with_for_update() if for_update else query).one_or_none()
    if conn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Connection not found")
    return conn


def _out(session: Session, conn: Connection) -> ConnectionOut:
    cred = session.get(Credential, conn.id)
    live = cred is not None and cred.revoked_at is None and conn.state != "disconnected"
    schedules = session.scalars(select(SyncSchedule).where(SyncSchedule.connection_id == conn.id)
                                .order_by(SyncSchedule.dataset)).all()
    return ConnectionOut(
        id=str(conn.id), provider=conn.provider, account_ref=conn.account_ref,
        display_name=conn.display_name, state=conn.state, state_reason=conn.state_reason,
        scopes=list(conn.scopes or []), created_at=conn.created_at, updated_at=conn.updated_at,
        has_credential=live, credential_expires_at=cred.expires_at if live and cred else None,
        schedules=[ScheduleOut(dataset=s.dataset, kind=s.kind, cron=s.cron, timezone=s.timezone,
                               jitter_s=s.jitter_s, overlap=s.overlap, catchup_window_s=s.catchup_window_s,
                               lookback_s=s.lookback_s, paused=s.paused, next_due_at=s.next_due_at)
                   for s in schedules])


def _audit(session: Session, current: CurrentWorkspace, principal: Principal, action: str,
           conn: Connection, detail: dict[str, Any] | None = None) -> None:
    audit.record(session, workspace_id=current.workspace.id, actor_type="user", actor_id=principal.user_id,
                 action=action, target_type="connection", target_id=str(conn.id), detail=detail)


def _set_state(conn: Connection, state: str, reason: str | None = None) -> None:
    conn.state = state
    conn.state_reason = reason
    conn.updated_at = datetime.now(UTC)


def _store_credential(session: Session, vault: Vault, conn: Connection, creds: CredentialsIn) -> None:
    """Insert or replace. The version always goes up, so a worker still holding the old credential
    loses its rotation check instead of overwriting the new one."""
    blob = vault.seal(conn.id, creds.secret())
    now = datetime.now(UTC)
    cred = session.get(Credential, conn.id, with_for_update=True)
    if cred is None:
        session.add(Credential(connection_id=conn.id, ciphertext=blob, key_id=vault.key_id, version=1,
                               expires_at=creds.expires_at, updated_at=now))
        return
    cred.ciphertext = blob
    cred.key_id = vault.key_id
    cred.version = cred.version + 1
    cred.expires_at = creds.expires_at
    cred.refreshed_at = None
    cred.revoked_at = None
    cred.updated_at = now


# ---- routes

Current = Annotated[CurrentWorkspace, Depends(current_workspace)]
Db = Annotated[Session, Depends(get_session)]
Who = Annotated[Principal, Depends(require_principal)]


@router.get("", response_model=list[ConnectionOut])
def list_connections(current: Current, session: Db) -> list[ConnectionOut]:
    rows = session.scalars(select(Connection).where(Connection.workspace_id == current.workspace.id)
                           .order_by(Connection.created_at, Connection.id)).all()
    return [_out(session, c) for c in rows]


@router.get("/{connection_id}", response_model=ConnectionOut)
def get_connection(connection_id: uuid.UUID, current: Current, session: Db) -> ConnectionOut:
    return _out(session, _get(session, current, connection_id))


@router.post("", status_code=201, response_model=ConnectionOut)
def create_connection(body: CreateConnection, current: Current, principal: Who, session: Db,
                      vault: Annotated[Vault, Depends(_vault)]) -> ConnectionOut:
    _owner(current)
    duplicate = HTTPException(status.HTTP_409_CONFLICT, "This account is already connected; reconnect it instead")
    if session.scalars(select(Connection.id).where(
            Connection.workspace_id == current.workspace.id, Connection.provider == body.provider,
            Connection.account_ref == body.account_ref)).first() is not None:
        raise duplicate
    now = datetime.now(UTC)
    conn = Connection(id=uuid.uuid4(), workspace_id=current.workspace.id, provider=body.provider,
                      account_ref=body.account_ref, display_name=body.display_name, state="healthy",
                      scopes=body.scopes, config=dict(body.config), created_at=now, updated_at=now)
    try:
        with session.begin_nested():  # a duplicate rolls back only this savepoint
            session.add(conn)
    except IntegrityError:  # lost a race with an identical create (the unique constraint in 0004)
        raise duplicate from None
    _store_credential(session, vault, conn, body.credentials)
    _audit(session, current, principal, "connection.create", conn,
           {"provider": conn.provider, "account_ref": conn.account_ref})
    session.commit()
    return _out(session, conn)


@router.post("/{connection_id}/pause", response_model=ConnectionOut)
def pause_connection(connection_id: uuid.UUID, current: Current, principal: Who, session: Db) -> ConnectionOut:
    _owner(current)
    conn = _get(session, current, connection_id, for_update=True)
    if conn.state == "paused":
        return _out(session, conn)
    if conn.state != "healthy":
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {conn.state} connection cannot be paused")
    _set_state(conn, "paused", "paused by an operator")
    _audit(session, current, principal, "connection.pause", conn, {"from_state": "healthy"})
    session.commit()
    return _out(session, conn)


@router.post("/{connection_id}/resume", response_model=ConnectionOut)
def resume_connection(connection_id: uuid.UUID, current: Current, principal: Who, session: Db) -> ConnectionOut:
    _owner(current)
    conn = _get(session, current, connection_id, for_update=True)
    if conn.state == "healthy":
        return _out(session, conn)
    if conn.state != "paused":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A {conn.state} connection cannot be resumed; reconnect it instead")
    _set_state(conn, "healthy")
    _audit(session, current, principal, "connection.resume", conn, {"from_state": "paused"})
    session.commit()
    return _out(session, conn)


@router.post("/{connection_id}/reconnect", response_model=ConnectionOut)
def reconnect_connection(connection_id: uuid.UUID, body: ReconnectIn, current: Current, principal: Who,
                         session: Db, vault: Annotated[Vault, Depends(_vault)]) -> ConnectionOut:
    _owner(current)
    conn = _get(session, current, connection_id, for_update=True)
    previous = conn.state
    _store_credential(session, vault, conn, body.credentials)
    _set_state(conn, "healthy")
    _audit(session, current, principal, "connection.reconnect", conn, {"from_state": previous})
    session.commit()
    return _out(session, conn)


@router.post("/{connection_id}/disconnect", response_model=ConnectionOut)
def disconnect_connection(connection_id: uuid.UUID, current: Current, principal: Who,
                          session: Db) -> ConnectionOut:
    """Destroys the stored secret (the row stays, emptied and revoked, so its version keeps rising)."""
    _owner(current)
    conn = _get(session, current, connection_id, for_update=True)
    if conn.state == "disconnected":
        return _out(session, conn)
    previous = conn.state
    cred = session.get(Credential, conn.id, with_for_update=True)
    if cred is not None:
        now = datetime.now(UTC)
        cred.ciphertext = b""
        cred.version = cred.version + 1
        cred.revoked_at = now
        cred.updated_at = now
    _set_state(conn, "disconnected", "disconnected by an operator")
    _audit(session, current, principal, "connection.disconnect", conn, {"from_state": previous})
    session.commit()
    return _out(session, conn)


@router.put("/{connection_id}/schedules/{dataset}", response_model=ConnectionOut)
def upsert_schedule(connection_id: uuid.UUID, dataset: DATASET, body: ScheduleIn, current: Current,
                    principal: Who, session: Db) -> ConnectionOut:
    _owner(current)
    conn = _get(session, current, connection_id, for_update=True)
    if conn.state == "disconnected":
        raise HTTPException(status.HTTP_409_CONFLICT, "A disconnected connection has no schedules")
    sched = session.get(SyncSchedule, (conn.id, dataset), with_for_update=True)
    created = sched is None
    if sched is None:
        sched = SyncSchedule(connection_id=conn.id, dataset=dataset)
        session.add(sched)
    for name, value in body.model_dump().items():
        setattr(sched, name, value)
    sched.next_due_at = None  # the scheduler recomputes it from the new cron
    _audit(session, current, principal, "connection.schedule_upsert", conn,
           {"dataset": dataset, "created": created} | body.model_dump())
    session.commit()
    session.refresh(conn)
    return _out(session, conn)

