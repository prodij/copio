"""`make bootstrap`: configure the local Zitadel, Lago and S3 storage once. Safe to re-run.

Every step looks before it creates, so a failed run is fixed by fixing the cause and running again.
IDs go to .bootstrap/ids.env and the backend's token to .bootstrap/backend/backend.pat (both
git-ignored); Compose reads them. Checked against Zitadel v4.20.0 and Lago v1.55.0.

scripts/brand.py imports `env`, `zitadel_admin_token`, `zitadel_endpoint` and `lago_graphql`.
"""

import functools
import os
import subprocess
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

import product

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".bootstrap"
IDS = STATE / "ids.env"
FRONTEND_ENV = STATE / "frontend.env"
ADMIN_PAT = STATE / "zitadel" / "admin.pat"
BACKEND_PAT = STATE / "backend" / "backend.pat"
LAGO_WEBHOOK_URL = "http://backend:8000/billing/webhooks/lago"
USAGE_METRIC = "reports_generated"
ROLES = {"owner": "Owner", "member": "Member"}
# Zitadel answers 400 with one of these when an update would change nothing.
ZITADEL_NO_CHANGES = ("No changes", "COMMAND-1m88i", "COMMAND-SsfG5")


# -- configuration ---------------------------------------------------------------------------


def env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"{name} is not set; run `make env` (it writes .env) and fill it in")
    return value


def on_aws() -> bool:
    return os.environ.get("DEPLOY_TARGET") == "aws"


def public_url(sub: str, port_var: str) -> str:
    if on_aws():
        return f"https://{sub}.{env('DOMAIN')}"
    host = f"{sub}.{product.DOMAIN}" if sub else product.DOMAIN
    return f"http://{host}:{env(port_var)}"


def app_url() -> str:
    return public_url("app", "APP_PORT") if on_aws() else public_url("", "APP_PORT")


def zitadel_url() -> str:
    return public_url("auth", "ZITADEL_PORT")


def lago_api_url() -> str:
    return public_url("lago-api", "LAGO_API_PORT")


def local(url: str) -> tuple[str, dict[str, str]]:
    """Where this process reaches a public URL.

    Locally: 127.0.0.1 plus the Host header the service routes on (Zitadel picks its instance by Host,
    and not every resolver maps *.localhost to 127.0.0.1). On AWS: Zitadel through its public URL, and
    Lago on loopback, because Caddy keeps its public API closed.
    """
    parts = urlsplit(url)
    if on_aws():
        if parts.netloc.startswith("lago-api."):
            return "http://127.0.0.1:3000", {"Host": parts.netloc, "X-Forwarded-Proto": "https"}
        return url, {}
    return f"http://127.0.0.1:{parts.port}", {"Host": parts.netloc}


def client(url: str, headers: dict[str, str] | None = None) -> httpx.Client:
    base, host = local(url)
    return httpx.Client(base_url=base, headers={**host, **(headers or {})}, timeout=30.0)


def zitadel_endpoint() -> tuple[str, dict[str, str]]:
    return local(zitadel_url())


# -- small helpers ---------------------------------------------------------------------------


def check(response: httpx.Response, what: str) -> dict[str, Any]:
    if response.is_error:
        raise SystemExit(f"bootstrap: {what} failed: HTTP {response.status_code} {response.text[:400]}")
    body: dict[str, Any] = response.json() if response.content else {}
    return body


def write_ids(path: Path, ids: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}={v}\n" for k, v in ids.items()))


def read_ids(path: Path | None = None) -> dict[str, str]:
    path = path or IDS  # looked up per call, so tests (and callers) can point IDS elsewhere
    if not path.exists():
        return {}
    pairs = (line.split("=", 1) for line in path.read_text().splitlines() if "=" in line)
    return {k: v for k, v in pairs}


def save_ids(**ids: str) -> None:
    write_ids(IDS, read_ids() | ids)


def compose(*args: str, capture: bool = False) -> str:
    try:
        result = subprocess.run(  # noqa: S603 (fixed program, our own arguments)
            ["docker", "compose", *args],  # noqa: S607
            cwd=ROOT, check=True, text=True, capture_output=capture,
        )
    except FileNotFoundError as exc:
        raise SystemExit("bootstrap: `docker` is not installed or not on PATH") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip()[-400:]
        raise SystemExit(f"bootstrap: `docker compose {' '.join(args[:3])}` failed (exit {exc.returncode}) {detail}") from exc
    return result.stdout.strip() if capture else ""


def wait_for(what: str, ready: Any, timeout: float = 300.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if ready():
                return
        except (httpx.HTTPError, OSError):
            pass
        time.sleep(2)
    raise SystemExit(
        f"bootstrap: timed out waiting for {what}; is `make up` running? (`make logs`). If the local "
        "data is from an older setup, `make reset` deletes it and `make up` starts fresh."
    )


def http_ok(url: str, path: str) -> bool:
    with client(url) as http:
        return http.get(path).status_code == 200


# -- Zitadel ---------------------------------------------------------------------------------


def zitadel_admin_token() -> str:
    """The instance admin PAT that Zitadel's first start wrote into the bind-mounted .bootstrap/zitadel."""
    if not ADMIN_PAT.is_file():
        raise SystemExit(f"bootstrap: {ADMIN_PAT.relative_to(ROOT)} not found; run `make up` and wait for Zitadel")
    return ADMIN_PAT.read_text().strip()


def zitadel_http() -> httpx.Client:
    return client(zitadel_url(), {"Authorization": f"Bearer {zitadel_admin_token()}"})


def ensure_project(http: httpx.Client, name: str) -> str:
    found = check(http.post("/management/v1/projects/_search", json={"queries": [
        {"nameQuery": {"name": name, "method": "TEXT_QUERY_METHOD_EQUALS"}}]}), "Zitadel project search")
    project_id = next((str(p["id"]) for p in found.get("result", []) if p["name"] == name), None)
    if project_id is None:
        created = check(http.post("/management/v1/projects", json={
            "name": name, "projectRoleAssertion": True}), "Zitadel project create")
        project_id = str(created["id"])
    roles = check(http.post(f"/management/v1/projects/{project_id}/roles/_search", json={}),
                  "Zitadel role search")
    existing = {r["key"] for r in roles.get("result", [])}
    missing = [{"key": k, "displayName": v} for k, v in ROLES.items() if k not in existing]
    if missing:
        check(http.post(f"/management/v1/projects/{project_id}/roles/_bulk", json={"roles": missing}),
              "Zitadel role create")
    return project_id


def web_app_config(app: str) -> dict[str, Any]:
    """OIDC settings for the browser app: PKCE code flow, JWT access tokens carrying roles."""
    return {
        "redirectUris": [f"{app}/callback"],
        "postLogoutRedirectUris": [f"{app}/"],
        "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
        "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE", "OIDC_GRANT_TYPE_REFRESH_TOKEN"],
        "appType": "OIDC_APP_TYPE_USER_AGENT",
        "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
        "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
        "accessTokenRoleAssertion": True,
        "idTokenRoleAssertion": True,
        "devMode": not on_aws(),  # local redirect URIs are http://
    }


def ensure_web_app(http: httpx.Client, project_id: str, app: str) -> str:
    found = check(http.post(f"/management/v1/projects/{project_id}/apps/_search", json={}),
                  "Zitadel app search")
    existing = next((a for a in found.get("result", []) if a["name"] == "web"), None)
    if existing is None:
        created = check(http.post(f"/management/v1/projects/{project_id}/apps/oidc",
                                  json={"name": "web", **web_app_config(app)}), "Zitadel app create")
        return str(created["clientId"])
    # Keep the redirect URIs in step with APP_PORT if it changed since the first run.
    update = http.put(f"/management/v1/projects/{project_id}/apps/{existing['id']}/oidc_config",
                      json=web_app_config(app))
    if not (update.status_code == 400 and any(m in update.text for m in ZITADEL_NO_CHANGES)):
        check(update, "Zitadel app update")
    return str(existing["oidcConfig"]["clientId"])


def backend_pat_works(http: httpx.Client) -> bool:
    """False when there is no PAT yet, or it belongs to an instance since wiped (`down -v`)."""
    if not BACKEND_PAT.is_file():
        return False
    me = http.get("/auth/v1/users/me", headers={"Authorization": f"Bearer {BACKEND_PAT.read_text().strip()}"})
    if me.status_code in (401, 403):
        return False
    check(me, "Zitadel backend token check")
    return True


def ensure_backend_machine_user(http: httpx.Client) -> None:
    """Machine user `backend`: creates workspace orgs, grants the project to them, adds members."""
    found = check(http.post("/management/v1/users/_search", json={"queries": [
        {"userNameQuery": {"userName": "backend", "method": "TEXT_QUERY_METHOD_EQUALS"}}]}),
        "Zitadel user search")
    user_id = next((str(u["id"]) for u in found.get("result", [])), None)
    if user_id is None:
        user = check(http.post("/management/v1/users/machine", json={
            "userName": "backend", "name": "Backend", "accessTokenType": "ACCESS_TOKEN_TYPE_BEARER"}),
            "Zitadel machine user create")
        user_id = str(user["userId"])
    # IAM_ORG_MANAGER: create and manage every organization; ORG_OWNER on the instance org: grant
    # the project that lives there. 409 = already a member.
    for path, role in (("/admin/v1/members", "IAM_ORG_MANAGER"), ("/management/v1/orgs/me/members", "ORG_OWNER")):
        member = http.post(path, json={"userId": user_id, "roles": [role]})
        if member.status_code != 409:
            check(member, f"Zitadel {role} membership")
    if not backend_pat_works(http):
        pat = check(http.post(f"/management/v1/users/{user_id}/pats", json={}), "Zitadel PAT create")
        BACKEND_PAT.parent.mkdir(parents=True, exist_ok=True)
        BACKEND_PAT.write_text(pat["token"])
        BACKEND_PAT.chmod(0o600)


LOGIN_POLICY_FIELDS = (
    "allowUsernamePassword", "allowRegister", "allowExternalIdp", "forceMfa", "forceMfaLocalOnly",
    "passwordlessType", "hidePasswordReset", "ignoreUnknownUsernames", "defaultRedirectUri",
    "passwordCheckLifetime", "externalLoginCheckLifetime", "mfaInitSkipLifetime",
    "secondFactorCheckLifetime", "multiFactorCheckLifetime", "allowDomainDiscovery",
    "disableLoginWithEmail", "disableLoginWithPhone",
)


def ensure_self_registration(http: httpx.Client) -> None:
    """Instance login policy: allow sign-up with username and password; every other field kept."""
    policy = check(http.get("/admin/v1/policies/login"), "Zitadel login policy read")["policy"]
    if policy.get("allowRegister") and policy.get("allowUsernamePassword"):
        return
    body = {k: policy[k] for k in LOGIN_POLICY_FIELDS if k in policy}
    body |= {"allowRegister": True, "allowUsernamePassword": True}
    check(http.put("/admin/v1/policies/login", json=body), "Zitadel login policy update")


def ensure_login_page(http: httpx.Client) -> None:
    """Zitadel stores the login page's URL at first start, so a moved ZITADEL_LOGIN_PORT needs this."""
    base = f"{public_url('auth', 'ZITADEL_LOGIN_PORT')}/ui/v2/login/"
    feature = check(http.get("/v2/features/instance"), "Zitadel feature read").get("loginV2", {})
    if feature.get("baseUri") != base:
        check(http.put("/v2/features/instance", json={"loginV2": {"required": True, "baseUri": base}}),
              "Zitadel login page update")


def bootstrap_zitadel() -> None:
    with zitadel_http() as http:
        org_id = str(check(http.get("/management/v1/orgs/me"), "Zitadel org read")["org"]["id"])
        project_id = ensure_project(http, product.SLUG)
        client_id = ensure_web_app(http, project_id, app_url())
        ensure_backend_machine_user(http)
        ensure_self_registration(http)
        ensure_login_page(http)
    save_ids(ZITADEL_PROJECT_ID=project_id, ZITADEL_INSTANCE_ORG_ID=org_id, ZITADEL_CLIENT_ID=client_id)
    # The browser sees every ZITADEL_* variable the dev server has, so it gets only these two.
    write_ids(FRONTEND_ENV, {"ZITADEL_CLIENT_ID": client_id, "ZITADEL_PROJECT_ID": project_id})
    print(f"Zitadel: project {project_id}, web client {client_id}")


# -- Lago ------------------------------------------------------------------------------------

LOGIN = "mutation($i: LoginUserInput!){loginUser(input:$i){token user{organizations{id name}}}}"


@functools.cache
def lago_session() -> tuple[str, str]:
    """(JWT, organization id) for the seeded Lago user; GraphQL needs both on every call."""
    with client(lago_api_url()) as http:
        reply = http.post("/graphql", json={"query": LOGIN, "variables": {"i": {
            "email": env("LAGO_ORG_USER_EMAIL"), "password": env("LAGO_ORG_USER_PASSWORD")}}})
    body = check(reply, "Lago login")
    try:
        login = body["data"]["loginUser"]
        return str(login["token"]), str(login["user"]["organizations"][0]["id"])
    except (KeyError, IndexError, TypeError) as exc:
        raise SystemExit(f"bootstrap: Lago login failed: {str(body.get('errors') or body)[:400]}") from exc


def lago_graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """Run a Lago GraphQL operation as the seeded admin; returns `data`, exits on any error."""
    token, org_id = lago_session()
    headers = {"Authorization": f"Bearer {token}", "X-Lago-Organization": org_id}
    with client(lago_api_url(), headers) as http:
        body = check(http.post("/graphql", json={"query": query, "variables": variables}), "Lago GraphQL")
    if body.get("errors") or not isinstance(body.get("data"), dict):
        raise SystemExit(f"bootstrap: Lago GraphQL error: {str(body.get('errors') or body)[:400]}")
    data: dict[str, Any] = body["data"]
    return data


def lago_api() -> httpx.Client:
    return client(lago_api_url(), {"Authorization": f"Bearer {env('LAGO_API_KEY')}"})


def bootstrap_lago() -> None:
    _, org_id = lago_session()
    save_ids(LAGO_ORGANIZATION_ID=org_id)
    with lago_api() as api:
        hooks = check(api.get("/api/v1/webhook_endpoints"), "Lago webhook list")
        hook = next((h for h in hooks.get("webhook_endpoints", []) if h["webhook_url"] == LAGO_WEBHOOK_URL), None)
        wanted = {"webhook_endpoint": {"webhook_url": LAGO_WEBHOOK_URL, "signature_algo": "jwt"}}
        if hook is None:
            check(api.post("/api/v1/webhook_endpoints", json=wanted), "Lago webhook create")
        elif hook.get("signature_algo") != "jwt":  # the backend verifies only JWT signatures
            check(api.put(f"/api/v1/webhook_endpoints/{hook['lago_id']}", json=wanted), "Lago webhook update")
        metric = api.get(f"/api/v1/billable_metrics/{USAGE_METRIC}")
        if metric.status_code == 404:
            check(api.post("/api/v1/billable_metrics", json={"billable_metric": {
                "name": "Reports generated", "code": USAGE_METRIC, "aggregation_type": "count_agg"}}),
                "Lago billable metric create")
        else:
            check(metric, "Lago billable metric read")
    print(f"Lago: organization {org_id}, webhook to the backend, metric {USAGE_METRIC}")


STRIPE_PROVIDERS = "query{paymentProviders(type: stripe){collection{... on StripeProvider{id code successRedirectUrl}}}}"
ADD_STRIPE = "mutation($i: AddStripePaymentProviderInput!){addStripePaymentProvider(input:$i){id}}"
UPDATE_STRIPE = "mutation($i: UpdateStripePaymentProviderInput!){updateStripePaymentProvider(input:$i){id}}"
# Lago cannot register a Stripe webhook endpoint for a local URL, so it checks the signing secret
# of `stripe listen` instead (the CLI's secret is fixed per Stripe account). Adding the provider
# queues Lago's RegisterWebhookJob, which writes Stripe's own endpoint secret on success, so this
# runs last: it waits until no such job is queued or scheduled, then sets the CLI's secret unless
# Lago already has it (safe to repeat).
STRIPE_WEBHOOK_RUBY = """
require "sidekiq/api"
job = "PaymentProviders::Stripe::RegisterWebhookJob"
queued = -> { [Sidekiq::Queue.new("providers"), Sidekiq::ScheduledSet.new].any? { |s| s.any? { |j| j.display_class == job } } }
deadline = Time.now + 60
sleep 1 while queued.call && Time.now < deadline
provider = PaymentProviders::StripeProvider.find_by!(organization_id: ENV.fetch("LAGO_ORGANIZATION_ID"), code: "stripe")
secret = ENV.fetch("STRIPE_CLI_WEBHOOK_SECRET")
if provider.webhook_secret == secret
  puts "Lago already has the stripe listen webhook secret"
else
  provider.update!(webhook_secret: secret)
  puts "Lago now checks the stripe listen webhook secret"
end
"""


STRIPE_REJECTED = ("Stripe rejected STRIPE_SECRET_KEY or could not be reached. Nothing was changed. "
                   "Fix or empty it in .env and run `make bootstrap` again.")
KEY_NOT_CHECKED = ("could not check STRIPE_SECRET_KEY with Stripe: Stripe may have rejected it or be unreachable, "
                   "or Docker failed (details below). Nothing was changed. Fix the cause, or empty the key in .env, "
                   "and run `make bootstrap` again.")


def optional_env(name: str) -> str:
    """Make passes .env values as written, so `STRIPE_SECRET_KEY=""` arrives here with its quotes."""
    return os.environ.get(name, "").strip().strip("\"'").strip()


def stripe_secret_key() -> str:
    """The test key, or "" when none is set yet: Stripe is optional, a wrong kind of key is not."""
    key = optional_env("STRIPE_SECRET_KEY")
    if key and not key.startswith("sk_test_"):
        raise SystemExit(
            "bootstrap: STRIPE_SECRET_KEY must be a Stripe TEST secret key (sk_test_...), or empty to run "
            "without billing. Nothing was changed. Fix it in .env (test keys are at "
            "https://dashboard.stripe.com/test/apikeys) and run `make bootstrap` again."
        )
    return key


def stripe_webhook_secret() -> str:
    """The signing secret of `stripe listen`. Asking for it is what tests the key against Stripe."""
    try:
        printed = compose("run", "--rm", "--no-deps", "--entrypoint", "stripe", "stripe-cli",
                          "listen", "--print-secret", capture=True).splitlines()
    except SystemExit as exc:
        raise SystemExit(f"bootstrap: {KEY_NOT_CHECKED}\n  {exc}") from None
    secret = printed[-1].strip() if printed else ""
    if not secret.startswith("whsec_"):
        raise SystemExit(f"bootstrap: {STRIPE_REJECTED}\n  `stripe listen --print-secret` printed no whsec_ secret")
    return secret


def mock_payment() -> bool:
    """BILLING_MODE=mock: the same refusals as the backend's, before anything changes."""
    mode = optional_env("BILLING_MODE")
    if not mode:
        return False
    if mode != "mock":
        raise SystemExit(f"bootstrap: BILLING_MODE must be empty or mock, not {mode!r}. Nothing was changed.")
    if optional_env("APP_ENV") != "local":
        raise SystemExit("bootstrap: mock payment is refused: BILLING_MODE=mock needs APP_ENV=local. Nothing was changed.")
    if stripe_secret_key():
        raise SystemExit("bootstrap: mock payment is refused: STRIPE_SECRET_KEY is set. Empty it or empty BILLING_MODE "
                         "in .env. Nothing was changed.")
    return True


def lago_has_subscriptions() -> bool:
    """Any at all: Lago's list answers only active ones unless asked for each status."""
    with lago_api() as api:
        reply = api.get("/api/v1/subscriptions", params={
            "status[]": ["pending", "active", "terminated", "canceled", "incomplete"], "per_page": 1})
    return bool(check(reply, "Lago subscription list")["subscriptions"])


def check_lago_matches_billing_mode(mock: bool) -> None:
    """Stops a stack that changed billing mode, before services are recreated or a provider is added.

    Real checkout needs the provider before it can make a subscription, so a subscription with no provider
    can only have come from mock payment. A normal re-run and adding a first key both pass.
    """
    has_provider = bool(lago_graphql(STRIPE_PROVIDERS, {})["paymentProviders"]["collection"])
    if mock and has_provider:
        raise SystemExit("bootstrap: mock payment is refused: Lago still has the Stripe provider from an earlier key "
                         "and could call Stripe. `make reset` deletes all local data; then `make up && make bootstrap`.")
    if not mock and not has_provider and lago_has_subscriptions():
        raise SystemExit("bootstrap: Lago's subscriptions are left over from mock payment, and their premium access "
                         "would look real. `make reset` deletes all local data; then `make up && make bootstrap`.")


def print_mock_payment_on() -> None:
    print("Mock payment: ON (BILLING_MODE=mock, APP_ENV=local). Nothing is charged and Stripe is not called. Real Lago "
          "and its signed webhook still decide access.\n  A mock payment pass is not a Stripe pass.")


def bootstrap_stripe(webhook_secret: str) -> None:
    key = stripe_secret_key()
    if not key:  # stripe-cli stays idle: scripts/stripe-listen.sh exits 0 without a key
        print("Stripe: SKIPPED, STRIPE_SECRET_KEY is empty. The app works, but billing isn't set up, so plans "
              "can't be bought.\n  To add it: paste a test key (sk_test_..., from "
              "https://dashboard.stripe.com/test/apikeys) into .env and run `make bootstrap` again.")
        return
    providers = lago_graphql(STRIPE_PROVIDERS, {})["paymentProviders"]["collection"]
    provider = next((p for p in providers if p.get("code") == "stripe"), None)
    return_url = f"{app_url()}/billing/return"
    if provider is None:
        lago_graphql(ADD_STRIPE, {"i": {"name": "Stripe", "code": "stripe", "secretKey": key,
                                        "successRedirectUrl": return_url}})
    elif provider.get("successRedirectUrl") != return_url:  # APP_PORT moved. Stays in Lago: Stripe isn't called.
        lago_graphql(UPDATE_STRIPE, {"i": {"id": provider["id"], "successRedirectUrl": return_url}})
    if on_aws():  # no stripe-cli here: LAGO_API_URL is public, so Lago's RegisterWebhookJob registers its own webhook
        print("Stripe: Lago connected; Lago registers its own webhook with Stripe")
        return
    compose("up", "-d", "--force-recreate", "stripe-cli")
    apply_stripe_webhook_secret(webhook_secret)  # last: after any RegisterWebhookJob could have run
    print("Stripe: Lago connected; `stripe listen` forwards test webhooks to Lago")


def apply_stripe_webhook_secret(secret: str) -> None:
    _, org_id = lago_session()
    compose("exec", "-T", "-e", f"LAGO_ORGANIZATION_ID={org_id}", "-e", f"STRIPE_CLI_WEBHOOK_SECRET={secret}",
            "lago-api", "bin/rails", "runner", STRIPE_WEBHOOK_RUBY)


# -- S3 storage, backend ---------------------------------------------------------------------


def ensure_bucket(name: str = "data") -> None:
    """Create the jobs' bucket in SeaweedFS unless `s3.bucket.list` shows it (`weed shell`, which
    talks to the master inside the container, prints its results on stderr)."""
    if on_aws():
        return  # Terraform creates the bucket
    shell = "weed shell -master=localhost:9333 2>&1"
    script = (f"echo s3.bucket.list | {shell} | grep -qE '^>? *{name}[[:space:]]' "
              f"|| echo 's3.bucket.create -name {name}' | {shell} | grep -q 'created bucket {name}'")

    last_error = ""

    def done() -> bool:  # fails until SeaweedFS has a leader and a filer, some time after `make up`
        nonlocal last_error
        command = ["docker", "compose", "exec", "-T", "s3", "sh", "-c", script]
        try:
            result = subprocess.run(command, cwd=ROOT, check=False, capture_output=True, timeout=30)  # noqa: S603
        except subprocess.TimeoutExpired:
            last_error = "`weed shell` did not answer within 30 s"
            return False
        last_error = (result.stderr or b"").decode(errors="replace").strip()[-400:]
        return result.returncode == 0

    try:
        wait_for(f"S3 bucket {name}", done, timeout=120.0)
    except SystemExit as exc:
        raise SystemExit(f"{exc} Last error: {last_error}" if last_error else str(exc)) from None


def publish_aws_state() -> None:
    import boto3

    import aws_state

    ids = read_ids()
    region, slug = env("AWS_REGION"), env("SLUG")
    aws_state.publish_frontend(
        boto3.client("ssm", region_name=region), slug,
        aws_state.frontend_values(env("DOMAIN"), ids["ZITADEL_CLIENT_ID"], ids["ZITADEL_PROJECT_ID"]))
    aws_state.save_tokens(boto3.client("secretsmanager", region_name=region), slug, STATE)


def backend(*args: str) -> None:
    compose("exec", "-T", "backend", "uv", "run", "--no-dev", *args)


def main() -> None:
    # First: a wrong key, or one Stripe rejects, stops before anything changes. The backend must not
    # get a key Lago has no provider for, or new workspaces fail. Saved back so Compose, which prefers
    # this process's environment over .env, gets the cleaned value.
    key = os.environ["STRIPE_SECRET_KEY"] = stripe_secret_key()
    os.environ["BILLING_MODE"], os.environ["APP_ENV"] = optional_env("BILLING_MODE"), optional_env("APP_ENV")
    mock = mock_payment()
    webhook_secret = stripe_webhook_secret() if key and not on_aws() else ""
    zitadel, lago = zitadel_url(), lago_api_url()
    wait_for(f"Zitadel at {zitadel}", lambda: http_ok(zitadel, "/debug/ready"))
    wait_for("Zitadel's admin token", ADMIN_PAT.is_file)  # written before Zitadel serves
    wait_for(f"Lago at {lago}", lambda: http_ok(lago, "/health"))
    bootstrap_zitadel()
    bootstrap_lago()
    if on_aws():  # first: brand needs Lago's S3, the likeliest first-deploy failure, and tokens must survive it
        publish_aws_state()
    check_lago_matches_billing_mode(mock)
    ensure_bucket()
    if subprocess.run(["uv", "run", "python", "brand.py"], cwd=ROOT / "scripts", check=False).returncode:  # noqa: S607
        raise SystemExit("bootstrap: `make brand` failed (see above); fix it and run `make bootstrap` again")
    compose("up", "-d", "--force-recreate", "backend")  # picks up .bootstrap/ids.env and the PAT
    wait_for("the backend", lambda: http_ok(public_url("api", "API_PORT"), "/health"))
    backend("alembic", "upgrade", "head")  # needs only DATABASE_URL
    backend("python", "-m", "app.billing.sync")  # needs only the Lago settings
    compose("up", "-d", "--force-recreate", "jobs")  # its first run needs the migrated tables
    if mock:  # no provider is added and stripe-cli stays idle, so nothing here can reach Stripe
        print_mock_payment_on()
    else:
        bootstrap_stripe(webhook_secret)  # the backend already has the key: it was recreated from the same .env
    if not on_aws():  # on AWS the frontend isn't deployed yet
        # Last: the app gets its client id only once everything behind it is configured.
        compose("up", "-d", "--force-recreate", "frontend")
        wait_for(f"the app at {app_url()}", lambda: http_ok(app_url(), "/"))  # it runs `npm ci` first
    s3_line = "" if on_aws() else f"\n  S3           http://localhost:{env('S3_PORT')} (SeaweedFS, bucket data)"
    print(f"""
Ready.
  App          {app_url()}
  API          {public_url("api", "API_PORT")}
  Zitadel      {zitadel}/ui/console
  Lago         {public_url("lago", "LAGO_FRONT_PORT")}{s3_line}
Open {app_url()}""")


if __name__ == "__main__":
    try:
        main()
    except httpx.HTTPError as exc:
        raise SystemExit(f"bootstrap: request failed ({type(exc).__name__}): {exc}") from None
