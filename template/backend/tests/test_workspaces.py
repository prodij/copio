import json

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.workspaces import service
from app.workspaces.models import Workspace
from tests.auth_helpers import AuthHeaders
from tests.fakes import LAGO, ZITADEL, fake_lago, fake_zitadel


@respx.mock
def test_create_workspace_happy_path(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    lago = fake_lago(respx.mock)
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1"))
    assert r.status_code == 201
    ws = db_session.scalars(select(Workspace)).one()
    assert r.json() == {"id": str(ws.id), "name": "Acme", "status": "ready"}
    assert (ws.status, ws.zitadel_org_id, ws.zitadel_grant_id, ws.lago_customer_id) == (
        "ready", str(ws.id), "grant-1", "lago-cust-1"
    )
    org_body = json.loads(z["org"].calls.last.request.content)
    assert org_body == {"name": f"Acme ({str(ws.id)[:8]})", "organizationId": str(ws.id)}
    grant = z["grant"].calls.last.request
    assert grant.headers["x-zitadel-orgid"] == "org-instance"
    assert json.loads(grant.content) == {"grantedOrgId": str(ws.id), "roleKeys": ["owner", "member"]}
    user_grant = z["user_grant"].calls.last.request
    assert user_grant.url.path == "/management/v1/users/user-1/grants"
    assert user_grant.headers["x-zitadel-orgid"] == str(ws.id)
    assert json.loads(user_grant.content) == {"projectId": "proj-1", "projectGrantId": "grant-1", "roleKeys": ["owner"]}
    customer = json.loads(lago["customer"].calls.last.request.content)["customer"]
    assert customer["external_id"] == str(ws.id)
    assert customer["billing_configuration"]["payment_provider"] == "stripe"


@respx.mock
def test_second_create_returns_existing_workspace(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    headers = auth("user-1")
    first = client.post("/workspaces", json={"name": "Acme"}, headers=headers).json()
    second = client.post("/workspaces", json={"name": "Acme again"}, headers=headers)
    assert second.status_code == 200
    assert second.json() == first
    assert z["org"].call_count == 1
    assert len(db_session.scalars(select(Workspace)).all()) == 1


@respx.mock
def test_lago_down_returns_503_and_resumable(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    respx.post(f"{LAGO}/api/v1/customers").mock(return_value=httpx.Response(502))
    headers = auth("user-1")
    r = client.post("/workspaces", json={"name": "Acme"}, headers=headers)
    assert r.status_code == 503
    assert r.json() == {"detail": "Lago is unavailable"}
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.status, ws.zitadel_org_id, ws.lago_customer_id) == ("creating", str(ws.id), None)

    respx.post(f"{LAGO}/api/v1/customers").mock(
        return_value=httpx.Response(200, json={"customer": {"lago_id": "lago-cust-1"}})
    )
    r = client.post("/workspaces", json={"name": "Acme"}, headers=headers)
    assert r.status_code == 201
    assert (z["org"].call_count, z["grant"].call_count) == (1, 1)
    assert db_session.scalars(select(Workspace)).one().status == "ready"


@respx.mock
def test_role_grant_failure_is_resumable(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    z["user_grant"].mock(return_value=httpx.Response(503))
    headers = auth("user-1")
    r = client.post("/workspaces", json={"name": "Acme"}, headers=headers)
    assert r.status_code == 503
    assert r.json() == {"detail": "Zitadel is unavailable"}
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.status, ws.zitadel_org_id, ws.zitadel_grant_id) == ("creating", str(ws.id), "grant-1")

    z["user_grant"].mock(return_value=httpx.Response(200, json={"userGrantId": "ug-1"}))
    assert client.post("/workspaces", json={"name": "Acme"}, headers=headers).status_code == 201
    assert (z["org"].call_count, z["grant"].call_count) == (1, 1)


@respx.mock
def test_retry_after_lost_zitadel_responses_reuses_what_exists(
    client: TestClient, auth: AuthHeaders, db_session: Session
) -> None:
    """Zitadel created everything but the answers never arrived: 409s must resume, not fail."""
    z = fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    z["org"].mock(return_value=httpx.Response(409, json={"code": 6, "message": "Errors.Org.AlreadyExisting"}))
    z["grant"].mock(return_value=httpx.Response(409, json={"code": 6, "message": "Errors.Project.Grant.AlreadyExists"}))
    z["user_grant"].mock(return_value=httpx.Response(409, json={"code": 6, "message": "Errors.UserGrant.AlreadyExists"}))
    search = respx.post(f"{ZITADEL}/management/v1/projectgrants/_search").mock(
        return_value=httpx.Response(200, json={"result": [{"grantId": "grant-old", "grantedOrgId": "x"}]})
    )
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1"))
    assert r.status_code == 201
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.zitadel_org_id, ws.zitadel_grant_id) == (str(ws.id), "grant-old")
    assert json.loads(search.calls.last.request.content) == {"queries": [
        {"projectIdQuery": {"projectId": "proj-1"}},
        {"grantedOrgIdQuery": {"grantedOrgId": str(ws.id)}},
    ]}


@respx.mock
def test_concurrent_first_create_resumes_the_winners_row(
    client: TestClient, auth: AuthHeaders, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second request that looked before the first one inserted must not 500 on the unique owner."""
    fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    winner = Workspace(name="Acme", owner_user_id="user-1", status="creating")
    db_session.add(winner)
    db_session.commit()
    monkeypatch.setattr(service, "_owned_workspace", lambda _session, _user_id: None)
    r = client.post("/workspaces", json={"name": "Acme too"}, headers=auth("user-1"))
    assert r.status_code == 201
    assert r.json() == {"id": str(winner.id), "name": "Acme", "status": "ready"}
    assert len(db_session.scalars(select(Workspace)).all()) == 1


@respx.mock
def test_grant_search_lagging_behind_409_returns_503(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    z = fake_zitadel(respx.mock)
    z["grant"].mock(return_value=httpx.Response(409, json={"code": 6, "message": "Errors.Project.Grant.AlreadyExists"}))
    respx.post(f"{ZITADEL}/management/v1/projectgrants/_search").mock(return_value=httpx.Response(200, json={}))
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1"))
    assert r.status_code == 503
    assert r.json() == {"detail": "Zitadel is unavailable"}
    ws = db_session.scalars(select(Workspace)).one()
    assert (ws.status, ws.zitadel_grant_id) == ("creating", None)


@respx.mock
def test_zitadel_timeout_returns_503(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    respx.post(f"{ZITADEL}/v2/organizations").mock(side_effect=httpx.ConnectTimeout("t"))
    r = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1"))
    assert r.status_code == 503
    assert r.json() == {"detail": "Zitadel is unavailable"}
    assert db_session.scalars(select(Workspace)).one().status == "creating"


def test_me_without_workspace(client: TestClient, auth: AuthHeaders) -> None:
    r = client.get("/me", headers=auth("user-1", email="a@b.c"))
    assert r.json() == {"user_id": "user-1", "email": "a@b.c", "workspace": None}


@respx.mock
def test_me_with_workspace(client: TestClient, auth: AuthHeaders) -> None:
    fake_zitadel(respx.mock)
    fake_lago(respx.mock)
    ws = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1")).json()
    r = client.get("/me", headers=auth("user-1", {ws["id"]: "owner"}))
    assert r.json()["workspace"] == {"id": ws["id"], "name": "Acme", "role": "owner"}


def _ready_workspace(db_session: Session, owner: str, org_id: str, status: str = "ready") -> Workspace:
    ws = Workspace(name=f"WS {owner}", owner_user_id=owner, zitadel_org_id=org_id, status=status)
    db_session.add(ws)
    db_session.flush()
    return ws


def test_workspace_header_picks_among_several(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    _ready_workspace(db_session, "owner-a", "org-a")
    b = _ready_workspace(db_session, "owner-b", "org-b")
    headers = auth("user-1", {"org-a": "owner", "org-b": "member"})
    r = client.get("/me/workspace", headers=headers | {"X-Workspace-Id": str(b.id)})
    assert r.json() == {"id": str(b.id), "name": "WS owner-b", "role": "member"}


def test_workspace_header_for_foreign_workspace_is_forbidden(
    client: TestClient, auth: AuthHeaders, db_session: Session
) -> None:
    _ready_workspace(db_session, "owner-a", "org-a")
    other = _ready_workspace(db_session, "owner-b", "org-b")
    headers = auth("user-1", {"org-a": "owner"}) | {"X-Workspace-Id": str(other.id)}
    assert client.get("/me/workspace", headers=headers).status_code == 403


def test_workspace_still_creating_is_forbidden(client: TestClient, auth: AuthHeaders, db_session: Session) -> None:
    _ready_workspace(db_session, "owner-a", "org-a", status="creating")
    assert client.get("/me/workspace", headers=auth("owner-a", {"org-a": "owner"})).status_code == 403


def test_unknown_org_is_forbidden(client: TestClient, auth: AuthHeaders) -> None:
    r = client.get("/me/workspace", headers=auth("user-1", {"org-unknown": "owner"}))
    assert r.status_code == 403


def test_missing_token_is_401(client: TestClient) -> None:
    assert client.post("/workspaces", json={"name": "x"}).status_code == 401


@pytest.mark.parametrize("name", ["", " ", "x" * 81])
def test_bad_names_are_422(client: TestClient, auth: AuthHeaders, name: str) -> None:
    r = client.post("/workspaces", json={"name": name}, headers=auth("user-1"))
    assert r.status_code == 422
