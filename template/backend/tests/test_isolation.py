"""Architecture tests: every route is authenticated or on the public list, and a member of one
workspace cannot reach another workspace's data through any route (spec §10, "Isolation")."""

import uuid

import pytest
import respx
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.deps import require_principal
from app.billing.models import Subscription
from app.main import create_app
from app.workspaces.models import Workspace
from app.workspaces.routes import current_workspace
from tests.auth_helpers import AuthHeaders

PUBLIC = {"/health", "/billing/plans", "/billing/webhooks/lago"}
# Signed in but not inside a workspace yet: creating the first one, and "who am I". Everything else
# must go through current_workspace.
PRINCIPAL_ONLY = {"/workspaces", "/me"}
# A valid body per route that takes one, so a 403 is the workspace check and not body validation.
BODIES: dict[str, dict[str, str]] = {"/billing/checkout": {"plan_code": "starter"}}


def _deps(route: RouteContext) -> set[object]:
    seen: set[object] = set()
    stack = list(route.dependant.dependencies)
    while stack:
        d = stack.pop()
        seen.add(d.call)
        stack.extend(d.dependencies)
    return seen


def _routes() -> list[RouteContext]:
    """Every API route with its full path. FastAPI 0.162 keeps included routers as nested entries
    in `app.routes`, so a plain `isinstance(route, APIRoute)` loop would see only `/health`."""
    return [r for r in iter_route_contexts(create_app().routes) if isinstance(r.original_route, APIRoute)]


WORKSPACE_ROUTES = [(m, str(r.path)) for r in _routes() if current_workspace in _deps(r) for m in sorted(r.methods or ())]


def test_every_route_is_public_principal_only_or_workspace_scoped() -> None:
    paths = {r.path for r in _routes()}
    assert PUBLIC | PRINCIPAL_ONLY | {"/billing/checkout"} <= paths  # the walk sees them
    for route in _routes():
        deps = _deps(route)
        if route.path in PRINCIPAL_ONLY:
            assert require_principal in deps, route.path
        elif route.path not in PUBLIC:
            assert current_workspace in deps, f"{route.path} must depend on current_workspace"


def test_the_workspace_routes_are_the_expected_ones() -> None:
    # Guards the parametrization below: a new workspace route is covered without editing this file.
    assert {("GET", "/me/workspace"), ("GET", "/me/access"), ("GET", "/demo/premium-report"),
            ("POST", "/billing/checkout")} <= set(WORKSPACE_ROUTES)


@pytest.fixture
def other_workspace(db_session: Session) -> Workspace:
    """Another user's ready workspace with an active plan, so any leak would be visible."""
    other = Workspace(name="Other", owner_user_id="u-other", zitadel_org_id="org-other", status="ready")
    db_session.add(other)
    db_session.flush()
    db_session.add(Subscription(workspace_id=other.id, plan_code="starter", state="active"))
    db_session.flush()
    return other


@pytest.mark.parametrize(("method", "path"), WORKSPACE_ROUTES)
def test_workspace_header_cannot_reach_other_workspace(client: TestClient, owner_headers: dict[str, str],
                                                       other_workspace: Workspace, method: str, path: str) -> None:
    for target in (str(other_workspace.id), str(uuid.uuid4())):
        with respx.mock:  # no Lago or Zitadel call may happen
            r = client.request(method, path, json=BODIES.get(path),
                               headers=owner_headers | {"X-Workspace-Id": target})
        assert r.status_code == 403, (method, path, r.text)


def test_own_workspace_never_sees_another_workspaces_plan(client: TestClient, owner_headers: dict[str, str],
                                                          owner_workspace: str, other_workspace: Workspace) -> None:
    with respx.mock:
        me = client.get("/me", headers=owner_headers)
        access = client.get("/me/access", headers=owner_headers)
        report = client.get("/demo/premium-report", headers=owner_headers)
    assert me.json()["workspace"]["id"] == owner_workspace
    assert access.json() == {"billing_configured": True, "plan_code": None, "state": None,
                             "current_period_end": None, "features": {}}
    assert report.status_code == 402


def test_a_token_role_for_a_workspace_that_is_not_ready_grants_nothing(client: TestClient, auth: AuthHeaders,
                                                                       db_session: Session) -> None:
    creating = Workspace(name="Half", owner_user_id="u-half", zitadel_org_id="org-half", status="creating")
    db_session.add(creating)
    db_session.flush()
    r = client.get("/me/workspace", headers=auth("u-half", {"org-half": "owner"}))
    assert r.status_code == 403
