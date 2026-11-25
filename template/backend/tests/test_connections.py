"""Connection routes: credentials stay write-only, every change is audited, and workspaces are isolated."""

import logging
import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditEvent
from app.connectors import vault as vault_module
from app.connectors.models import Connection, Credential, SyncSchedule
from app.connectors.routes import _vault
from app.connectors.vault import Vault, vault_from_env
from app.workspaces.models import Workspace
from tests.auth_helpers import AuthHeaders

TOKEN = "synthetic-secret-token-abc123"
TOKEN_2 = "synthetic-secret-token-xyz789"
REFRESH = "synthetic-refresh-qrs456"
SECRETS = (TOKEN, TOKEN_2, REFRESH)
KEK = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="


@pytest.fixture
def vault() -> Vault:
    return vault_from_env({"CONNECTOR_LOCAL_KEK": KEK})


@pytest.fixture
def api(client: TestClient, vault: Vault, caplog: pytest.LogCaptureFixture) -> Iterator[TestClient]:
    """The client with the test vault. Every log line of the test is checked for secrets at the end."""
    client.app.dependency_overrides[_vault] = lambda: vault  # type: ignore[attr-defined]
    caplog.set_level(logging.DEBUG)
    yield client
    for secret in SECRETS:
        assert secret not in caplog.text


def body(**overrides: Any) -> dict[str, Any]:
    return {"provider": "synthetic", "account_ref": "acct-1", "display_name": "Synthetic shop",
            "scopes": ["read"], "credentials": {"access_token": TOKEN, "extra": {"refresh_token": REFRESH}}
            } | overrides


def no_secret(text: str) -> None:
    for secret in SECRETS:
        assert secret not in text


def create(api: TestClient, headers: dict[str, str], **overrides: Any) -> dict[str, Any]:
    r = api.post("/connections", json=body(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    no_secret(r.text)
    return dict(r.json())


def events(db: Session, connection_id: str) -> list[AuditEvent]:
    return list(db.scalars(select(AuditEvent).where(AuditEvent.target_id == connection_id)
                           .order_by(AuditEvent.id)))


@pytest.fixture
def workspace_b(db_session: Session, auth: AuthHeaders) -> dict[str, str]:
    """Another ready workspace, owned by user-b. Returns its owner's headers."""
    ws = Workspace(name="B", owner_user_id="user-b", zitadel_org_id="org-b", status="ready")
    db_session.add(ws)
    db_session.flush()
    return auth("user-b", {"org-b": "owner"})


# ---- create and read


def test_create_stores_only_ciphertext_and_audits(api: TestClient, owner_headers: dict[str, str],
                                                  owner_workspace: str, db_session: Session,
                                                  vault: Vault) -> None:
    out = create(api, owner_headers)
    assert out["state"] == "healthy"
    assert out["has_credential"] is True
    assert "credentials" not in out and "access_token" not in out
    cid = uuid.UUID(out["id"])
    cred = db_session.get(Credential, cid)
    assert cred is not None and cred.version == 1 and cred.key_id == vault.key_id
    assert TOKEN.encode() not in cred.ciphertext
    secret = vault.open(cid, cred.ciphertext)
    assert (secret.access_token, dict(secret.extra)) == (TOKEN, {"refresh_token": REFRESH})
    (event,) = events(db_session, out["id"])
    assert (str(event.workspace_id), event.actor_type, event.actor_id, event.action) == (
        owner_workspace, "user", "user-1", "connection.create")
    no_secret(str(event.detail))

    listed = api.get("/connections", headers=owner_headers)
    assert [c["id"] for c in listed.json()] == [out["id"]]
    no_secret(listed.text)
    one = api.get(f"/connections/{out['id']}", headers=owner_headers)
    assert one.json() == out


@pytest.mark.parametrize("payload", [
    body(provider="not-synthetic"),
    body(credentials=[TOKEN]),  # the whole credentials value is invalid: FastAPI would echo it
    body(credentials={"access_token": TOKEN + "x" * 9000}),  # too long: FastAPI would echo the token
    body(credentials={"access_token": TOKEN, "expires_at": "not-a-date", "extra": {"r": REFRESH}}),
    body(credentials={"access_token": TOKEN, "extra": {"k": [REFRESH]}}),
])
def test_validation_errors_never_echo_credentials(api: TestClient, owner_headers: dict[str, str],
                                                  payload: dict[str, Any]) -> None:
    r = api.post("/connections", json=payload, headers=owner_headers)
    assert r.status_code == 422
    no_secret(r.text)
    assert r.json()["detail"][0]["loc"][0] == "body"


def test_a_member_cannot_create(api: TestClient, owner_workspace: str, auth: AuthHeaders) -> None:
    r = api.post("/connections", json=body(), headers=auth("user-2", {owner_workspace: "member"}))
    assert r.status_code == 403
    assert api.get("/connections", headers=auth("user-2", {owner_workspace: "member"})).json() == []


def test_the_same_account_twice_is_a_conflict(api: TestClient, owner_headers: dict[str, str],
                                              db_session: Session) -> None:
    create(api, owner_headers)
    r = api.post("/connections", json=body(), headers=owner_headers)
    assert r.status_code == 409
    no_secret(r.text)
    assert len(api.get("/connections", headers=owner_headers).json()) == 1


def test_a_misconfigured_vault_is_a_503_without_values(client: TestClient, owner_headers: dict[str, str],
                                                       monkeypatch: pytest.MonkeyPatch) -> None:
    vault_module._cached_vault.cache_clear()
    monkeypatch.setenv("CONNECTOR_LOCAL_KEK", KEK)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("CONNECTOR_KMS_KEY_ID", raising=False)
    r = client.post("/connections", json=body(), headers=owner_headers)
    vault_module._cached_vault.cache_clear()
    assert r.status_code == 503
    assert "CONNECTOR_KMS_KEY_ID" in r.text
    assert KEK not in r.text
    no_secret(r.text)


# ---- state changes


def test_pause_resume(api: TestClient, owner_headers: dict[str, str], db_session: Session) -> None:
    cid = create(api, owner_headers)["id"]
    assert api.post(f"/connections/{cid}/pause", headers=owner_headers).json()["state"] == "paused"
    assert api.post(f"/connections/{cid}/pause", headers=owner_headers).json()["state"] == "paused"
    assert api.post(f"/connections/{cid}/resume", headers=owner_headers).json()["state"] == "healthy"
    assert [e.action for e in events(db_session, cid)] == [
        "connection.create", "connection.pause", "connection.resume"]


def test_reconnect_needed_cannot_pause_or_resume_but_reconnects(api: TestClient, owner_headers: dict[str, str],
                                                                db_session: Session, vault: Vault) -> None:
    cid = create(api, owner_headers)["id"]
    conn = db_session.get(Connection, uuid.UUID(cid))
    assert conn is not None
    conn.state, conn.state_reason = "reconnect_needed", "provider_auth_revoked"
    db_session.flush()
    assert api.post(f"/connections/{cid}/pause", headers=owner_headers).status_code == 409
    assert api.post(f"/connections/{cid}/resume", headers=owner_headers).status_code == 409

    r = api.post(f"/connections/{cid}/reconnect", headers=owner_headers,
                 json={"credentials": {"access_token": TOKEN_2}})
    assert r.status_code == 200, r.text
    no_secret(r.text)
    assert (r.json()["state"], r.json()["state_reason"], r.json()["has_credential"]) == ("healthy", None, True)
    cred = db_session.get(Credential, uuid.UUID(cid))
    assert cred is not None
    db_session.refresh(cred)
    assert cred.version == 2 and cred.revoked_at is None
    assert vault.open(uuid.UUID(cid), cred.ciphertext).access_token == TOKEN_2
    last = events(db_session, cid)[-1]
    assert (last.action, last.detail) == ("connection.reconnect", {"from_state": "reconnect_needed"})


def test_disconnect_destroys_the_secret_and_reconnect_brings_it_back(
        api: TestClient, owner_headers: dict[str, str], db_session: Session, vault: Vault) -> None:
    cid = create(api, owner_headers)["id"]
    r = api.post(f"/connections/{cid}/disconnect", headers=owner_headers)
    assert (r.json()["state"], r.json()["has_credential"]) == ("disconnected", False)
    cred = db_session.get(Credential, uuid.UUID(cid))
    assert cred is not None
    db_session.refresh(cred)
    assert cred.ciphertext == b"" and cred.revoked_at is not None and cred.version == 2
    assert api.post(f"/connections/{cid}/disconnect", headers=owner_headers).status_code == 200
    assert api.post(f"/connections/{cid}/resume", headers=owner_headers).status_code == 409

    r = api.post(f"/connections/{cid}/reconnect", headers=owner_headers,
                 json={"credentials": {"access_token": TOKEN_2}})
    assert r.json()["state"] == "healthy"
    db_session.refresh(cred)
    assert cred.version == 3  # never reused, so a worker's stale rotation can't win
    assert [e.action for e in events(db_session, cid)] == [
        "connection.create", "connection.disconnect", "connection.reconnect"]


def test_reconnect_validation_errors_never_echo(api: TestClient, owner_headers: dict[str, str]) -> None:
    cid = create(api, owner_headers)["id"]
    r = api.post(f"/connections/{cid}/reconnect", headers=owner_headers, json={"credentials": TOKEN_2})
    assert r.status_code == 422
    no_secret(r.text)


def test_a_member_cannot_change_a_connection(api: TestClient, owner_headers: dict[str, str],
                                             owner_workspace: str, auth: AuthHeaders) -> None:
    cid = create(api, owner_headers)["id"]
    member = auth("user-2", {owner_workspace: "member"})
    for path in ("pause", "resume", "disconnect"):
        assert api.post(f"/connections/{cid}/{path}", headers=member).status_code == 403
    assert api.put(f"/connections/{cid}/schedules/orders", headers=member,
                   json={"cron": "0 * * * *"}).status_code == 403
    assert api.get(f"/connections/{cid}", headers=member).json()["state"] == "healthy"


# ---- schedules


def test_schedule_upsert(api: TestClient, owner_headers: dict[str, str], db_session: Session) -> None:
    cid = create(api, owner_headers)["id"]
    r = api.put(f"/connections/{cid}/schedules/orders", headers=owner_headers,
                json={"cron": "*/15  * * * *", "timezone": "Europe/Berlin", "jitter_s": 30})
    assert r.status_code == 200, r.text
    (sched,) = r.json()["schedules"]
    assert (sched["dataset"], sched["cron"], sched["timezone"], sched["overlap"]) == (
        "orders", "*/15 * * * *", "Europe/Berlin", "skip")
    r = api.put(f"/connections/{cid}/schedules/orders", headers=owner_headers,
                json={"cron": "0 3 * * *", "overlap": "queue_one", "paused": True})
    (sched,) = r.json()["schedules"]
    assert (sched["cron"], sched["overlap"], sched["paused"], sched["timezone"]) == (
        "0 3 * * *", "queue_one", True, "UTC")
    rows = db_session.scalars(select(SyncSchedule).where(SyncSchedule.connection_id == uuid.UUID(cid))).all()
    assert len(rows) == 1
    upserts = [e for e in events(db_session, cid) if e.action == "connection.schedule_upsert"]
    assert [e.detail["created"] for e in upserts] == [True, False]


@pytest.mark.parametrize(("dataset", "payload"), [
    ("orders", {"cron": "every hour"}),
    ("orders", {"cron": "0 * * * *", "timezone": "Mars/Olympus"}),
    ("orders", {"cron": "0 * * * *", "overlap": "pile_up"}),
    ("orders", {"cron": "0 * * * *", "jitter_s": -1}),
    ("Orders!", {"cron": "0 * * * *"}),
])
def test_bad_schedules_are_refused(api: TestClient, owner_headers: dict[str, str], dataset: str,
                                   payload: dict[str, Any]) -> None:
    cid = create(api, owner_headers)["id"]
    assert api.put(f"/connections/{cid}/schedules/{dataset}", headers=owner_headers,
                   json=payload).status_code == 422


def test_a_disconnected_connection_takes_no_schedule(api: TestClient, owner_headers: dict[str, str]) -> None:
    cid = create(api, owner_headers)["id"]
    api.post(f"/connections/{cid}/disconnect", headers=owner_headers)
    assert api.put(f"/connections/{cid}/schedules/orders", headers=owner_headers,
                   json={"cron": "0 * * * *"}).status_code == 409


# ---- isolation


def test_workspace_b_cannot_see_or_change_workspace_a(api: TestClient, owner_headers: dict[str, str],
                                                      workspace_b: dict[str, str], db_session: Session) -> None:
    cid = create(api, owner_headers)["id"]
    assert api.get("/connections", headers=workspace_b).json() == []
    assert api.get(f"/connections/{cid}", headers=workspace_b).status_code == 404
    for path in ("pause", "resume", "disconnect"):
        r = api.post(f"/connections/{cid}/{path}", headers=workspace_b)
        assert r.status_code == 404, path
    r = api.post(f"/connections/{cid}/reconnect", headers=workspace_b,
                 json={"credentials": {"access_token": TOKEN_2}})
    assert r.status_code == 404
    assert api.put(f"/connections/{cid}/schedules/orders", headers=workspace_b,
                   json={"cron": "0 * * * *"}).status_code == 404
    # A's connection is untouched and B's audit trail is empty.
    a = api.get(f"/connections/{cid}", headers=owner_headers).json()
    assert (a["state"], a["schedules"]) == ("healthy", [])
    assert [e.action for e in events(db_session, cid)] == ["connection.create"]
    cred = db_session.get(Credential, uuid.UUID(cid))
    assert cred is not None and cred.version == 1


def test_the_same_account_can_be_connected_in_two_workspaces(api: TestClient, owner_headers: dict[str, str],
                                                             workspace_b: dict[str, str]) -> None:
    a = create(api, owner_headers)
    b = create(api, workspace_b)
    assert a["id"] != b["id"]
    assert [c["id"] for c in api.get("/connections", headers=workspace_b).json()] == [b["id"]]


def test_unknown_connection_is_404(api: TestClient, owner_headers: dict[str, str]) -> None:
    assert api.post(f"/connections/{uuid.uuid4()}/pause", headers=owner_headers).status_code == 404
