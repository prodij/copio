import json
import pathlib
import subprocess

import httpx
import pytest
import respx

import bootstrap
from bootstrap import (
    ensure_backend_machine_user,
    ensure_project,
    ensure_self_registration,
    ensure_web_app,
    env,
    lago_graphql,
    local,
    read_ids,
    write_ids,
)

Z = "http://z"


def body(route: respx.Route) -> dict[str, object]:
    parsed: dict[str, object] = json.loads(route.calls.last.request.content)
    return parsed


def test_ids_roundtrip(tmp_path: pathlib.Path) -> None:
    write_ids(tmp_path / "ids.env", {"ZITADEL_PROJECT_ID": "p1", "ZITADEL_CLIENT_ID": "c1"})
    assert read_ids(tmp_path / "ids.env") == {"ZITADEL_PROJECT_ID": "p1", "ZITADEL_CLIENT_ID": "c1"}


def test_env_missing_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LAGO_API_KEY", raising=False)
    with pytest.raises(SystemExit, match="LAGO_API_KEY is not set; run `make env`"):
        env("LAGO_API_KEY")


def test_host_side_calls_go_to_loopback_with_the_public_host() -> None:
    assert local("http://auth.acme.localhost:8085") == (
        "http://127.0.0.1:8085", {"Host": "auth.acme.localhost:8085"})


@respx.mock
def test_ensure_project_reuses_existing() -> None:
    respx.post(f"{Z}/management/v1/projects/_search").respond(
        200, json={"result": [{"id": "p1", "name": "acme"}]})
    respx.post(f"{Z}/management/v1/projects/p1/roles/_search").respond(
        200, json={"result": [{"key": "owner"}, {"key": "member"}]})
    create = respx.post(f"{Z}/management/v1/projects").respond(200, json={"id": "p2"})
    roles = respx.post(f"{Z}/management/v1/projects/p1/roles/_bulk").respond(200, json={})
    with httpx.Client(base_url=Z) as http:
        assert ensure_project(http, "acme") == "p1"
    assert create.call_count == 0
    assert roles.call_count == 0


@respx.mock
def test_ensure_project_creates_with_role_assertion() -> None:
    respx.post(f"{Z}/management/v1/projects/_search").respond(200, json={"result": []})
    create = respx.post(f"{Z}/management/v1/projects").respond(200, json={"id": "p2"})
    respx.post(f"{Z}/management/v1/projects/p2/roles/_search").respond(200, json={})
    roles = respx.post(f"{Z}/management/v1/projects/p2/roles/_bulk").respond(200, json={})
    with httpx.Client(base_url=Z) as http:
        assert ensure_project(http, "acme") == "p2"
    assert body(create) == {"name": "acme", "projectRoleAssertion": True}
    assert [r["key"] for r in body(roles)["roles"]] == ["owner", "member"]  # type: ignore[attr-defined]


@respx.mock
def test_ensure_project_adds_roles_missing_after_an_interrupted_run() -> None:
    respx.post(f"{Z}/management/v1/projects/_search").respond(
        200, json={"result": [{"id": "p1", "name": "acme"}]})
    respx.post(f"{Z}/management/v1/projects/p1/roles/_search").respond(
        200, json={"result": [{"key": "owner"}]})
    roles = respx.post(f"{Z}/management/v1/projects/p1/roles/_bulk").respond(200, json={})
    with httpx.Client(base_url=Z) as http:
        ensure_project(http, "acme")
    assert body(roles) == {"roles": [{"key": "member", "displayName": "Member"}]}


@respx.mock
def test_zitadel_failure_is_a_readable_exit() -> None:
    respx.post(f"{Z}/management/v1/projects/_search").respond(403, json={"message": "no permission"})
    with httpx.Client(base_url=Z) as http, pytest.raises(
            SystemExit, match=r"Zitadel project search failed: HTTP 403 .*no permission"):
        ensure_project(http, "acme")


@respx.mock
def test_web_app_is_a_pkce_user_agent_app_with_jwt_role_tokens() -> None:
    respx.post(f"{Z}/management/v1/projects/p1/apps/_search").respond(200, json={})
    create = respx.post(f"{Z}/management/v1/projects/p1/apps/oidc").respond(
        200, json={"appId": "a1", "clientId": "c1"})
    with httpx.Client(base_url=Z) as http:
        assert ensure_web_app(http, "p1", "http://acme.localhost:5173") == "c1"
    sent = body(create)
    assert sent["redirectUris"] == ["http://acme.localhost:5173/callback"]
    assert sent["postLogoutRedirectUris"] == ["http://acme.localhost:5173/"]
    assert sent["appType"] == "OIDC_APP_TYPE_USER_AGENT"
    assert sent["authMethodType"] == "OIDC_AUTH_METHOD_TYPE_NONE"
    assert sent["grantTypes"] == ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"]
    assert sent["accessTokenType"] == "OIDC_TOKEN_TYPE_JWT"
    assert sent["accessTokenRoleAssertion"] is True and sent["devMode"] is True


@respx.mock
def test_existing_web_app_is_kept_and_its_unchanged_config_accepted() -> None:
    respx.post(f"{Z}/management/v1/projects/p1/apps/_search").respond(
        200, json={"result": [{"id": "a1", "name": "web", "oidcConfig": {"clientId": "c1"}}]})
    update = respx.put(f"{Z}/management/v1/projects/p1/apps/a1/oidc_config").respond(
        400, json={"code": 9, "message": "No changes (COMMAND-1m88i)"})
    create = respx.post(f"{Z}/management/v1/projects/p1/apps/oidc")
    with httpx.Client(base_url=Z) as http:
        assert ensure_web_app(http, "p1", "http://acme.localhost:5173") == "c1"
    assert update.call_count == 1
    assert create.call_count == 0


@respx.mock
def test_backend_user_gets_memberships_and_a_private_pat(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pat = tmp_path / "backend" / "backend.pat"
    monkeypatch.setattr(bootstrap, "BACKEND_PAT", pat)
    respx.post(f"{Z}/management/v1/users/_search").respond(200, json={})
    respx.post(f"{Z}/management/v1/users/machine").respond(200, json={"userId": "u1"})
    iam = respx.post(f"{Z}/admin/v1/members").respond(409, json={"message": "already exists"})
    org = respx.post(f"{Z}/management/v1/orgs/me/members").respond(200, json={})
    respx.post(f"{Z}/management/v1/users/u1/pats").respond(200, json={"token": "pat-1"})
    with httpx.Client(base_url=Z) as http:
        ensure_backend_machine_user(http)
    assert body(iam) == {"userId": "u1", "roles": ["IAM_ORG_MANAGER"]}
    assert body(org) == {"userId": "u1", "roles": ["ORG_OWNER"]}
    assert pat.read_text() == "pat-1"
    assert pat.stat().st_mode & 0o777 == 0o600


@respx.mock
@pytest.mark.parametrize(("status", "creates"), [(200, False), (401, True)])
def test_backend_pat_is_replaced_only_when_zitadel_rejects_it(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, status: int, creates: bool
) -> None:
    pat = tmp_path / "backend.pat"
    pat.write_text("old")
    monkeypatch.setattr(bootstrap, "BACKEND_PAT", pat)
    respx.post(f"{Z}/management/v1/users/_search").respond(200, json={"result": [{"id": "u1"}]})
    respx.post(f"{Z}/admin/v1/members").respond(409, json={})
    respx.post(f"{Z}/management/v1/orgs/me/members").respond(409, json={})
    me = respx.get(f"{Z}/auth/v1/users/me").respond(status, json={})
    create = respx.post(f"{Z}/management/v1/users/u1/pats").respond(200, json={"token": "new"})
    with httpx.Client(base_url=Z) as http:
        ensure_backend_machine_user(http)
    assert me.calls.last.request.headers["Authorization"] == "Bearer old"
    assert create.called is creates
    assert pat.read_text() == ("new" if creates else "old")


@respx.mock
def test_self_registration_changes_only_the_needed_fields() -> None:
    respx.get(f"{Z}/admin/v1/policies/login").respond(200, json={"policy": {
        "allowUsernamePassword": True, "allowRegister": False, "forceMfa": False,
        "passwordCheckLifetime": "864000s", "isDefault": True, "details": {}}})
    put = respx.put(f"{Z}/admin/v1/policies/login").respond(200, json={})
    with httpx.Client(base_url=Z) as http:
        ensure_self_registration(http)
    assert body(put) == {"allowUsernamePassword": True, "allowRegister": True, "forceMfa": False,
                         "passwordCheckLifetime": "864000s"}


@respx.mock
def test_self_registration_already_allowed_is_left_alone() -> None:
    respx.get(f"{Z}/admin/v1/policies/login").respond(200, json={"policy": {
        "allowUsernamePassword": True, "allowRegister": True}})
    put = respx.put(f"{Z}/admin/v1/policies/login")
    with httpx.Client(base_url=Z) as http:
        ensure_self_registration(http)
    assert put.call_count == 0


@pytest.fixture
def lago(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAGO_API_PORT", "3000")
    monkeypatch.setenv("LAGO_ORG_USER_EMAIL", "admin@acme.localhost")
    monkeypatch.setenv("LAGO_ORG_USER_PASSWORD", "pw")
    bootstrap.lago_session.cache_clear()


@respx.mock
@pytest.mark.usefixtures("lago")
def test_lago_graphql_sends_the_user_jwt_and_organization() -> None:
    route = respx.post("http://127.0.0.1:3000/graphql")
    route.side_effect = [
        httpx.Response(200, json={"data": {"loginUser": {"token": "jwt", "user": {"organizations": [{"id": "o1"}]}}}}),
        httpx.Response(200, json={"data": {"organization": {"id": "o1"}}}),
    ]
    assert lago_graphql("query{organization{id}}", {}) == {"organization": {"id": "o1"}}
    sent = route.calls.last.request
    assert sent.headers["Authorization"] == "Bearer jwt"
    assert sent.headers["X-Lago-Organization"] == "o1"
    assert sent.headers["Host"].startswith("lago-api.")


@respx.mock
@pytest.mark.usefixtures("lago")
def test_lago_graphql_errors_exit_readably() -> None:
    respx.post("http://127.0.0.1:3000/graphql").side_effect = [
        httpx.Response(200, json={"data": {"loginUser": {"token": "jwt", "user": {"organizations": [{"id": "o1"}]}}}}),
        httpx.Response(200, json={"data": None, "errors": [{"message": "forbidden"}]}),
    ]
    with pytest.raises(SystemExit, match=r"Lago GraphQL error: .*forbidden"):
        lago_graphql("query{organization{id}}", {})


@respx.mock
@pytest.mark.usefixtures("lago")
def test_lago_bad_login_exits_readably() -> None:
    respx.post("http://127.0.0.1:3000/graphql").respond(
        200, json={"data": {"loginUser": None}, "errors": [{"message": "incorrect_login_or_password"}]})
    with pytest.raises(SystemExit, match=r"Lago login failed: .*incorrect_login_or_password"):
        lago_graphql("query{organization{id}}", {})


def test_compose_failure_exits_readably(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise subprocess.CalledProcessError(1, "docker", stderr="service \"lago-api\" is not running")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(SystemExit, match=r"`docker compose exec -T lago-api` failed \(exit 1\).*not running"):
        bootstrap.compose("exec", "-T", "lago-api", "bin/rails")


@pytest.mark.parametrize("key", ["", "sk_live_x"])
def test_stripe_step_needs_a_test_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    with pytest.raises(SystemExit, match=r"STRIPE_SECRET_KEY must be a Stripe TEST secret key"):
        bootstrap.stripe_secret_key()


def test_admin_token_missing_is_clear(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "ADMIN_PAT", tmp_path / ".bootstrap" / "zitadel" / "admin.pat")
    with pytest.raises(SystemExit, match=r"admin.pat not found; run `make up`"):
        bootstrap.zitadel_admin_token()
