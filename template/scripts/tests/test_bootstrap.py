import json
import os
import pathlib
import subprocess

import httpx
import pytest
import respx

import bootstrap
import product
from bootstrap import (
    ensure_backend_machine_user,
    ensure_login_page,
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
@pytest.mark.parametrize(("status", "creates"), [(200, False), (401, True), (403, True)])
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


@respx.mock
def test_login_page_follows_a_moved_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZITADEL_LOGIN_PORT", "3120")
    wanted = f"http://auth.{bootstrap.product.DOMAIN}:3120/ui/v2/login/"
    respx.get(f"{Z}/v2/features/instance").respond(200, json={"loginV2": {
        "required": True, "baseUri": wanted.replace("3120", "3110")}})
    put = respx.put(f"{Z}/v2/features/instance").respond(200, json={})
    with httpx.Client(base_url=Z) as http:
        ensure_login_page(http)
    assert body(put) == {"loginV2": {"required": True, "baseUri": wanted}}


@respx.mock
def test_login_page_already_right_is_left_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZITADEL_LOGIN_PORT", "3100")
    respx.get(f"{Z}/v2/features/instance").respond(200, json={"loginV2": {
        "baseUri": f"http://auth.{bootstrap.product.DOMAIN}:3100/ui/v2/login/"}})
    put = respx.put(f"{Z}/v2/features/instance")
    with httpx.Client(base_url=Z) as http:
        ensure_login_page(http)
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


def test_bucket_step_waits_for_seaweedfs(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([1, 1, 0])
    scripts: list[str] = []

    def run(command: list[str], **_: object) -> subprocess.CompletedProcess[bytes]:
        scripts.append(command[-1])
        return subprocess.CompletedProcess(command, next(answers))

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    bootstrap.ensure_bucket()
    assert len(scripts) == 3
    assert "s3.bucket.create -name data" in scripts[0]


def test_bucket_step_gives_up_readably(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda c, **_: subprocess.CompletedProcess(c, 1))
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    monkeypatch.setattr(bootstrap.time, "monotonic", iter([0.0, 1.0, 500.0]).__next__)
    with pytest.raises(SystemExit, match="S3 bucket data"):
        bootstrap.ensure_bucket()


def test_bucket_step_reports_the_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda c, **_: subprocess.CompletedProcess(c, 1, b"", b"service s3 is not running\n"))
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    monkeypatch.setattr(bootstrap.time, "monotonic", iter([0.0, 1.0, 500.0]).__next__)
    with pytest.raises(SystemExit, match="Last error: service s3 is not running"):
        bootstrap.ensure_bucket()


def test_bucket_step_survives_a_hung_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    def hang(command: list[str], **kwargs: float) -> subprocess.CompletedProcess[bytes]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", hang)
    monkeypatch.setattr(bootstrap.time, "sleep", lambda _: None)
    monkeypatch.setattr(bootstrap.time, "monotonic", iter([0.0, 1.0, 500.0]).__next__)
    with pytest.raises(SystemExit, match="did not answer within 30 s"):
        bootstrap.ensure_bucket()


@pytest.mark.parametrize("key", ["sk_live_x", "rk_test_x", "whatever", "sk_live_x "])
def test_stripe_step_refuses_anything_but_a_test_key(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    with pytest.raises(SystemExit, match=r"STRIPE_SECRET_KEY must be a Stripe TEST secret key"):
        bootstrap.stripe_secret_key()


def test_admin_token_missing_is_clear(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "ROOT", tmp_path)
    monkeypatch.setattr(bootstrap, "ADMIN_PAT", tmp_path / ".bootstrap" / "zitadel" / "admin.pat")
    with pytest.raises(SystemExit, match=r"admin.pat not found; run `make up`"):
        bootstrap.zitadel_admin_token()


LAGO_API = "http://127.0.0.1:3000"
HOOK_URL = "http://backend:8000/billing/webhooks/lago"


@pytest.fixture
def lago_rest(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> pathlib.Path:
    monkeypatch.setenv("LAGO_API_PORT", "3000")
    monkeypatch.setenv("LAGO_API_KEY", "key")
    monkeypatch.setattr(bootstrap, "lago_session", lambda: ("jwt", "o1"))
    monkeypatch.setattr(bootstrap, "IDS", tmp_path / "ids.env")
    return tmp_path / "ids.env"


@respx.mock
def test_bootstrap_lago_creates_jwt_webhook_and_metric_once(lago_rest: pathlib.Path) -> None:
    respx.get(f"{LAGO_API}/api/v1/webhook_endpoints").respond(200, json={"webhook_endpoints": []})
    hook = respx.post(f"{LAGO_API}/api/v1/webhook_endpoints").respond(200, json={})
    respx.get(f"{LAGO_API}/api/v1/billable_metrics/reports_generated").respond(404, json={})
    metric = respx.post(f"{LAGO_API}/api/v1/billable_metrics").respond(200, json={})
    bootstrap.bootstrap_lago()
    assert body(hook) == {"webhook_endpoint": {"webhook_url": HOOK_URL, "signature_algo": "jwt"}}
    assert body(metric)["billable_metric"]["aggregation_type"] == "count_agg"  # type: ignore[index]
    assert read_ids(lago_rest) == {"LAGO_ORGANIZATION_ID": "o1"}


@respx.mock
def test_bootstrap_lago_leaves_existing_jwt_webhook_and_metric(lago_rest: pathlib.Path) -> None:
    respx.get(f"{LAGO_API}/api/v1/webhook_endpoints").respond(200, json={"webhook_endpoints": [
        {"lago_id": "h1", "webhook_url": HOOK_URL, "signature_algo": "jwt"}]})
    respx.get(f"{LAGO_API}/api/v1/billable_metrics/reports_generated").respond(200, json={"billable_metric": {}})
    writes = respx.route(method__in=["POST", "PUT"])
    bootstrap.bootstrap_lago()
    assert writes.call_count == 0


@respx.mock
def test_bootstrap_lago_switches_an_hmac_webhook_to_jwt(lago_rest: pathlib.Path) -> None:
    respx.get(f"{LAGO_API}/api/v1/webhook_endpoints").respond(200, json={"webhook_endpoints": [
        {"lago_id": "h1", "webhook_url": HOOK_URL, "signature_algo": "hmac"}]})
    update = respx.put(f"{LAGO_API}/api/v1/webhook_endpoints/h1").respond(200, json={})
    respx.get(f"{LAGO_API}/api/v1/billable_metrics/reports_generated").respond(200, json={})
    bootstrap.bootstrap_lago()
    assert body(update)["webhook_endpoint"]["signature_algo"] == "jwt"  # type: ignore[index]


class FakeStripeSetup:
    def __init__(self, monkeypatch: pytest.MonkeyPatch, providers: list[dict[str, str]], printed: str) -> None:
        self.graphql: list[tuple[str, dict[str, object]]] = []
        self.compose_calls: list[tuple[str, ...]] = []
        self.events: list[str] = []  # Compose calls and Lago GraphQL calls, in order
        self.providers, self.printed = providers, printed
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
        monkeypatch.setenv("APP_PORT", "5173")
        monkeypatch.setattr(bootstrap, "lago_session", lambda: ("jwt", "o1"))
        monkeypatch.setattr(bootstrap, "lago_graphql", self.lago_graphql)
        monkeypatch.setattr(bootstrap, "compose", self.compose)

    def lago_graphql(self, query: str, variables: dict[str, object]) -> dict[str, object]:
        self.graphql.append((query, variables))
        self.events.append(query)
        if query == bootstrap.STRIPE_PROVIDERS:
            return {"paymentProviders": {"collection": self.providers}}
        return {"addStripePaymentProvider": {"id": "p1"}}

    def compose(self, *args: str, capture: bool = False) -> str:
        self.compose_calls.append(args)
        self.events.append(" ".join(args))
        return self.printed if "--print-secret" in args else ""


@pytest.mark.parametrize("key", [None, "", " ", '""', "''", '" "'])
def test_bootstrap_stripe_is_skipped_plainly_without_a_key(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], key: str | None
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    if key is None:
        monkeypatch.delenv("STRIPE_SECRET_KEY")
    else:
        monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    bootstrap.bootstrap_stripe("")
    assert fake.graphql == [] and fake.compose_calls == []  # no provider, and stripe-cli is left idle
    out = capsys.readouterr().out
    assert "SKIPPED" in out and "STRIPE_SECRET_KEY" in out and "`make bootstrap` again" in out


@pytest.mark.parametrize("value", ["sk_test_x", ' sk_test_x ', '"sk_test_x"', "'sk_test_x'"])
def test_stripe_key_is_read_without_quotes_or_spaces(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", value)
    assert bootstrap.stripe_secret_key() == "sk_test_x"


@pytest.mark.parametrize("key", ["sk_live_x", "whatever"])
def test_main_stops_on_a_wrong_key_before_touching_anything(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    monkeypatch.setattr(bootstrap, "wait_for", lambda *_a, **_k: pytest.fail("a service was waited on"))
    with pytest.raises(SystemExit, match="Nothing was changed"):
        bootstrap.main()
    assert fake.compose_calls == [] and fake.graphql == []


@pytest.fixture
def stubbed_main(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Everything main() does apart from Stripe and Compose, stubbed; use with FakeStripeSetup."""
    for port in ("API_PORT", "ZITADEL_PORT", "LAGO_API_PORT", "LAGO_FRONT_PORT", "S3_PORT"):
        monkeypatch.setenv(port, "1234")
    for name in ("http_ok", "bootstrap_zitadel", "bootstrap_lago", "ensure_bucket", "backend"):
        monkeypatch.setattr(bootstrap, name, lambda *_a, **_k: True)
    monkeypatch.setattr(bootstrap, "lago_has_subscriptions", lambda: False)
    pat = tmp_path / "admin.pat"
    pat.write_text("x")
    monkeypatch.setattr(bootstrap, "ADMIN_PAT", pat)
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *_a, **_k: subprocess.CompletedProcess([], 0))


def test_main_tests_the_key_first_and_applies_the_webhook_secret_last(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc\n")
    bootstrap.main()
    assert sum("--print-secret" in c for c in fake.compose_calls) == 1  # fetched once, then reused
    assert "--print-secret" in fake.events[0]

    def at(text: str) -> int:
        return next(i for i, event in enumerate(fake.events) if text in event)

    assert at("--force-recreate backend") < at(bootstrap.ADD_STRIPE) < at("--force-recreate stripe-cli") < at("runner")
    assert at("runner") < at("--force-recreate frontend") == len(fake.events) - 1
    assert "STRIPE_CLI_WEBHOOK_SECRET=whsec_abc" in fake.events[at("runner")]


@pytest.mark.parametrize("printed", ["", "not a secret"])
def test_a_key_stripe_rejects_changes_nothing(monkeypatch: pytest.MonkeyPatch, stubbed_main: None, printed: str) -> None:
    fake = FakeStripeSetup(monkeypatch, [], printed)
    monkeypatch.setattr(bootstrap, "wait_for", lambda *_a, **_k: pytest.fail("a service was waited on"))
    with pytest.raises(SystemExit, match="Stripe rejected STRIPE_SECRET_KEY or could not be reached") as stopped:
        bootstrap.main()
    assert "Nothing was changed. Fix or empty it in .env and run `make bootstrap` again." in str(stopped.value)
    assert "printed no whsec_ secret" in str(stopped.value)
    assert len(fake.events) == 1 and "--print-secret" in fake.events[0]


def test_a_failed_print_secret_changes_nothing(monkeypatch: pytest.MonkeyPatch, stubbed_main: None) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "")

    def rejected(*_args: str, capture: bool = False) -> str:
        raise SystemExit("bootstrap: `docker compose run --rm --no-deps` failed (exit 1)")

    monkeypatch.setattr(bootstrap, "compose", rejected)
    monkeypatch.setattr(bootstrap, "wait_for", lambda *_a, **_k: pytest.fail("a service was waited on"))
    with pytest.raises(SystemExit, match="could not check STRIPE_SECRET_KEY with Stripe") as stopped:
        bootstrap.main()
    assert "or Docker failed" in str(stopped.value) and "Nothing was changed" in str(stopped.value)
    assert "failed (exit 1)" in str(stopped.value)
    assert "Stripe rejected" not in str(stopped.value)
    assert fake.graphql == []


@pytest.mark.parametrize("key", ["", '""'])
def test_main_finishes_without_a_key_and_recreates_the_frontend_last(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None, capsys: pytest.CaptureFixture[str], key: str
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    monkeypatch.setenv("STRIPE_SECRET_KEY", key)
    bootstrap.main()
    assert fake.compose_calls[-1] == ("up", "-d", "--force-recreate", "frontend")
    assert not any("stripe-cli" in call for call in fake.compose_calls)  # no print-secret either
    out = capsys.readouterr().out
    assert out.index("SKIPPED") < out.index("Ready.")
    assert os.environ["STRIPE_SECRET_KEY"] == ""  # what Compose gets: it would keep Make's literal quotes


def test_mock_payment_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BILLING_MODE", raising=False)
    monkeypatch.delenv("APP_ENV", raising=False)
    assert bootstrap.mock_payment() is False


@pytest.mark.parametrize(("env", "message"), [
    ({"BILLING_MODE": "fake"}, "must be empty or mock"),
    ({"BILLING_MODE": "mock", "APP_ENV": ""}, "needs APP_ENV=local"),
    ({"BILLING_MODE": "mock", "APP_ENV": "production"}, "needs APP_ENV=local"),
    ({"BILLING_MODE": "mock", "APP_ENV": "local", "STRIPE_SECRET_KEY": "sk_test_x"}, "STRIPE_SECRET_KEY is set"),
])
def test_main_refuses_unsafe_mock_payment_before_touching_anything(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], message: str
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(bootstrap, "wait_for", lambda *_a, **_k: pytest.fail("a service was waited on"))
    with pytest.raises(SystemExit, match=message) as stopped:
        bootstrap.main()
    assert "Nothing was changed" in str(stopped.value)
    assert fake.compose_calls == [] and fake.graphql == []


@pytest.mark.parametrize("quote", ["", '"', "'"])
def test_main_with_mock_payment_leaves_stripe_alone_and_says_so(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None, capsys: pytest.CaptureFixture[str], quote: str
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("BILLING_MODE", f"{quote}mock{quote}")
    monkeypatch.setenv("APP_ENV", f"{quote}local{quote}")
    bootstrap.main()
    assert not any("stripe-cli" in call for call in fake.compose_calls)  # no print-secret, no recreate
    assert all(query != bootstrap.ADD_STRIPE for query, _ in fake.graphql)
    assert fake.compose_calls[-1] == ("up", "-d", "--force-recreate", "frontend")
    out = capsys.readouterr().out
    assert "Mock payment: ON" in out and "not a Stripe pass" in out and "SKIPPED" not in out
    assert (os.environ["BILLING_MODE"], os.environ["APP_ENV"]) == ("mock", "local")  # what Compose gets, unquoted


def test_mock_payment_stops_on_a_stripe_provider_before_services_are_recreated(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None
) -> None:
    fake = FakeStripeSetup(monkeypatch, [{"id": "p1", "code": "stripe"}], "whsec_abc")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("BILLING_MODE", "mock")
    monkeypatch.setenv("APP_ENV", "local")
    with pytest.raises(SystemExit, match="Lago still has the Stripe provider"):
        bootstrap.main()
    assert fake.compose_calls == []


def test_leaving_mock_payment_stops_before_the_provider_is_added(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    monkeypatch.setenv("BILLING_MODE", "")
    monkeypatch.setattr(bootstrap, "lago_has_subscriptions", lambda: True)
    with pytest.raises(SystemExit, match=r"left over from mock payment.*`make reset`"):
        bootstrap.main()
    assert all(query != bootstrap.ADD_STRIPE for query, _ in fake.graphql)
    assert not any("--force-recreate" in call for call in fake.compose_calls)


def test_leaving_mock_payment_with_no_key_stops_too(monkeypatch: pytest.MonkeyPatch, stubbed_main: None) -> None:
    FakeStripeSetup(monkeypatch, [], "")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "")
    monkeypatch.setenv("BILLING_MODE", "")
    monkeypatch.setattr(bootstrap, "lago_has_subscriptions", lambda: True)
    with pytest.raises(SystemExit, match="left over from mock payment"):
        bootstrap.main()


def test_adding_a_first_key_is_not_taken_for_a_leftover(monkeypatch: pytest.MonkeyPatch, stubbed_main: None) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")  # no provider, no subscriptions
    monkeypatch.setenv("BILLING_MODE", "")
    bootstrap.main()
    assert any(query == bootstrap.ADD_STRIPE for query, _ in fake.graphql)


def test_a_rerun_with_a_provider_and_subscriptions_is_not_taken_for_a_leftover(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None
) -> None:
    fake = FakeStripeSetup(monkeypatch, [{"id": "p1", "code": "stripe"}], "whsec_abc")
    monkeypatch.setenv("BILLING_MODE", "")
    monkeypatch.setattr(bootstrap, "lago_has_subscriptions", lambda: pytest.fail("not needed with a provider"))
    bootstrap.main()
    assert fake.compose_calls[-1] == ("up", "-d", "--force-recreate", "frontend")


@respx.mock
def test_lago_subscriptions_are_asked_for_in_every_status(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LAGO_API_KEY", "k")
    monkeypatch.setenv("LAGO_API_PORT", "3000")
    route = respx.get("http://127.0.0.1:3000/api/v1/subscriptions").respond(200, json={"subscriptions": []})
    assert bootstrap.lago_has_subscriptions() is False
    assert route.calls.last.request.url.params.get_list("status[]") == [
        "pending", "active", "terminated", "canceled", "incomplete"]
    route.respond(200, json={"subscriptions": [{"external_id": "x"}]})
    assert bootstrap.lago_has_subscriptions() is True


def test_bootstrap_stripe_adds_the_provider_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc\n")
    bootstrap.bootstrap_stripe("whsec_abc")
    added = [v for q, v in fake.graphql if q == bootstrap.ADD_STRIPE]
    assert added == [{"i": {"name": "Stripe", "code": "stripe", "secretKey": "sk_test_x",
                            "successRedirectUrl": f"http://{product.DOMAIN}:5173/billing/return"}}]
    runner = next(c for c in fake.compose_calls if "runner" in c)
    assert "STRIPE_CLI_WEBHOOK_SECRET=whsec_abc" in runner and "LAGO_ORGANIZATION_ID=o1" in runner


def test_bootstrap_stripe_sets_the_webhook_secret_last(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lago's RegisterWebhookJob (queued when the provider is added) would overwrite the secret, so
    # the secret is written after everything else, each run, and only when Lago's value differs.
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    bootstrap.bootstrap_stripe("whsec_abc")
    bootstrap.bootstrap_stripe("whsec_abc")
    runs = [i for i, c in enumerate(fake.compose_calls) if "runner" in c]
    recreates = [i for i, c in enumerate(fake.compose_calls) if c == ("up", "-d", "--force-recreate", "stripe-cli")]
    assert len(runs) == len(recreates) == 2
    assert all(run > recreate for run, recreate in zip(runs, recreates, strict=True))
    assert fake.compose_calls[-1] == fake.compose_calls[runs[0]]
    ruby = bootstrap.STRIPE_WEBHOOK_RUBY
    assert ruby.index("RegisterWebhookJob") < ruby.index("sleep 1 while queued.call") < ruby.index("update!")
    assert "if provider.webhook_secret == secret" in ruby


def test_bootstrap_stripe_keeps_an_existing_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    current = f"http://{product.DOMAIN}:5173/billing/return"
    fake = FakeStripeSetup(monkeypatch, [{"id": "p1", "code": "stripe", "successRedirectUrl": current}], "whsec_abc")
    bootstrap.bootstrap_stripe("whsec_abc")
    assert [q for q, _ in fake.graphql] == [bootstrap.STRIPE_PROVIDERS]


def test_bootstrap_stripe_follows_a_moved_app_port_without_sending_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    stale = f"http://{product.DOMAIN}:5163/billing/return"
    fake = FakeStripeSetup(monkeypatch, [{"id": "p1", "code": "stripe", "successRedirectUrl": stale}], "whsec_abc")
    bootstrap.bootstrap_stripe("whsec_abc")
    assert [v for q, v in fake.graphql if q == bootstrap.UPDATE_STRIPE] == [
        {"i": {"id": "p1", "successRedirectUrl": f"http://{product.DOMAIN}:5173/billing/return"}}]


@pytest.mark.parametrize("printed", ["", "\n", "Getting ready...\nnot a secret"])
def test_stripe_webhook_secret_must_be_a_whsec_secret(monkeypatch: pytest.MonkeyPatch, printed: str) -> None:
    fake = FakeStripeSetup(monkeypatch, [{"id": "p1", "code": "stripe"}], printed)
    with pytest.raises(SystemExit, match="Stripe rejected STRIPE_SECRET_KEY"):
        bootstrap.stripe_webhook_secret()
    assert not any("runner" in c for c in fake.compose_calls)


@respx.mock
def test_backend_pat_check_other_errors_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pat = tmp_path / "backend.pat"
    pat.write_text("old")
    monkeypatch.setattr(bootstrap, "BACKEND_PAT", pat)
    respx.get(f"{Z}/auth/v1/users/me").respond(500, json={"message": "db down"})
    with httpx.Client(base_url=Z) as http, pytest.raises(SystemExit, match="backend token check failed: HTTP 500"):
        bootstrap.backend_pat_works(http)


def test_aws_urls_are_https_without_ports(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    assert bootstrap.zitadel_url() == "https://auth.x.test"
    assert bootstrap.app_url() == "https://app.x.test"
    assert bootstrap.public_url("api", "API_PORT") == "https://api.x.test"


def test_on_aws_zitadel_is_reached_publicly_and_lago_on_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    assert bootstrap.local("https://auth.x.test") == ("https://auth.x.test", {})
    assert bootstrap.local("https://lago-api.x.test") == (
        "http://127.0.0.1:3000", {"Host": "lago-api.x.test", "X-Forwarded-Proto": "https"})


def test_on_aws_redirects_must_be_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    assert bootstrap.web_app_config("https://app.x.test")["devMode"] is False


def test_locally_nothing_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEPLOY_TARGET", raising=False)
    monkeypatch.setenv("ZITADEL_PORT", "8085")
    assert bootstrap.zitadel_url().startswith("http://auth.")
    assert bootstrap.web_app_config("http://x.localhost:5173")["devMode"] is True


def test_on_aws_stripe_registers_no_local_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_x")
    calls: list[str] = []
    monkeypatch.setattr(bootstrap, "stripe_secret_key", lambda: "sk_test_x")
    monkeypatch.setattr(bootstrap, "lago_graphql", lambda q, v: {
        "paymentProviders": {"collection": [{"code": "stripe", "id": "p",
                                             "successRedirectUrl": "https://app.x.test/billing/return"}]}})
    monkeypatch.setattr(bootstrap, "compose", lambda *a, **k: calls.append(" ".join(a)) or "")
    monkeypatch.setattr(bootstrap, "apply_stripe_webhook_secret", lambda s: calls.append("secret"))
    bootstrap.bootstrap_stripe("")
    assert calls == []


def test_ensure_bucket_is_left_to_terraform_on_aws(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setattr(bootstrap, "wait_for", lambda *a, **k: pytest.fail("touched SeaweedFS"))
    bootstrap.ensure_bucket()


def test_aws_main_publishes_state_before_brand_and_touches_nothing_local(
    monkeypatch: pytest.MonkeyPatch, stubbed_main: None, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = FakeStripeSetup(monkeypatch, [], "whsec_abc")
    for name in list(os.environ):
        if name.endswith("_PORT"):
            monkeypatch.delenv(name)
    monkeypatch.setenv("DEPLOY_TARGET", "aws")
    monkeypatch.setenv("DOMAIN", "x.test")
    monkeypatch.setenv("AWS_REGION", "eu-west-2")
    monkeypatch.setenv("SLUG", "acme")
    monkeypatch.setattr(bootstrap, "publish_aws_state", lambda: fake.events.append("publish"))
    monkeypatch.setattr(bootstrap.subprocess, "run",
                        lambda *a, **_k: fake.events.append("brand") or subprocess.CompletedProcess([], 0))
    bootstrap.main()
    assert fake.events.index("publish") < fake.events.index("brand")
    text = " | ".join(fake.events)
    assert "--print-secret" not in text and "stripe-cli" not in text and "frontend" not in text.replace("publish", "")
    out = capsys.readouterr().out
    assert "gh workflow run deploy-frontend" in out and "Open " not in out and "S3 " not in out


def test_publish_aws_state_saves_tokens_before_the_frontend_values(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    from unittest.mock import MagicMock

    import boto3

    (tmp_path / "zitadel").mkdir()
    (tmp_path / "backend").mkdir()
    (tmp_path / "zitadel/admin.pat").write_text("A")
    (tmp_path / "zitadel/login-client.pat").write_text("L")
    (tmp_path / "backend/backend.pat").write_text("B")
    (tmp_path / "ids.env").write_text("ZITADEL_CLIENT_ID=c1\nZITADEL_PROJECT_ID=p1\n")
    monkeypatch.setattr(bootstrap, "STATE", tmp_path)
    monkeypatch.setattr(bootstrap, "IDS", tmp_path / "ids.env")
    for name, value in {"AWS_REGION": "eu-west-2", "SLUG": "acme", "DOMAIN": "x.test"}.items():
        monkeypatch.setenv(name, value)
    clients = {"ssm": MagicMock(), "secretsmanager": MagicMock()}
    order: list[str] = []
    clients["secretsmanager"].put_secret_value.side_effect = lambda **_k: order.append("tokens")
    clients["ssm"].put_parameter.side_effect = lambda **_k: order.append("frontend")
    monkeypatch.setattr(boto3, "client", lambda service, **_k: clients[service])
    bootstrap.publish_aws_state()
    assert order == ["tokens", "frontend"]
    assert clients["ssm"].put_parameter.call_args.kwargs["Name"] == "/acme/frontend"
    secret = clients["secretsmanager"].put_secret_value.call_args.kwargs
    assert secret["SecretId"] == "acme/bootstrap"
    assert set(json.loads(secret["SecretString"])) == {"admin_pat", "login_client_pat", "backend_pat", "ids_env"}


def test_publish_aws_state_turns_an_aws_error_into_a_plain_stop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    import boto3
    from botocore.exceptions import ClientError

    (tmp_path / "ids.env").write_text("ZITADEL_CLIENT_ID=c1\nZITADEL_PROJECT_ID=p1\n")
    monkeypatch.setattr(bootstrap, "IDS", tmp_path / "ids.env")
    for name, value in {"AWS_REGION": "eu-west-2", "SLUG": "acme", "DOMAIN": "x.test"}.items():
        monkeypatch.setenv(name, value)

    def denied(*_a: object, **_k: object) -> object:
        raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "secret-detail"}}, "PutSecretValue")

    from unittest.mock import MagicMock

    client = MagicMock()
    client.put_secret_value.side_effect = denied
    monkeypatch.setattr(boto3, "client", lambda *_a, **_k: client)
    (tmp_path / "zitadel").mkdir()
    (tmp_path / "backend").mkdir()
    for f in ("zitadel/admin.pat", "zitadel/login-client.pat", "backend/backend.pat"):
        (tmp_path / f).write_text("x")
    monkeypatch.setattr(bootstrap, "STATE", tmp_path)
    with pytest.raises(SystemExit, match=r"bootstrap: saving state to AWS failed \(ClientError AccessDeniedException\)") as stopped:
        bootstrap.publish_aws_state()
    assert "secret-detail" not in str(stopped.value)
