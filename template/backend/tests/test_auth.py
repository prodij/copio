import time
from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.deps import get_verifier, require_principal
from app.auth.principal import Principal
from app.auth.tokens import InvalidToken
from app.config import Settings
from tests.auth_helpers import TokenFactory


@pytest.fixture
def factory(settings: Settings) -> TokenFactory:
    return TokenFactory(settings)


def test_roles_are_read_per_org(factory: TokenFactory) -> None:
    token = factory.make("user-1", {"org-a": "owner", "org-b": "member"})
    principal = factory.verifier().verify(token)
    assert principal.user_id == "user-1"
    assert principal.roles_by_org == {"org-a": "owner", "org-b": "member"}


def test_owner_wins_when_both_roles(factory: TokenFactory) -> None:
    claims_key = f"urn:zitadel:iam:org:project:{factory.settings.zitadel_project_id}:roles"
    token = factory.make(
        "user-1", {}, **{claims_key: {"member": {"org-a": "a"}, "owner": {"org-a": "a"}}}
    )
    assert factory.verifier().verify(token).roles_by_org == {"org-a": "owner"}


def test_no_roles_is_allowed(factory: TokenFactory) -> None:
    assert factory.verifier().verify(factory.make("user-1", {})).roles_by_org == {}


@pytest.mark.parametrize(
    "override",
    [
        {"iss": "http://evil.test"},
        {"aud": ["other-project"]},
        {"exp": int(time.time()) - 10},
    ],
)
def test_bad_tokens_are_rejected(factory: TokenFactory, override: dict[str, object]) -> None:
    with pytest.raises(InvalidToken):
        factory.verifier().verify(factory.make("user-1", {}, **override))


def test_unsigned_garbage_is_rejected(factory: TokenFactory) -> None:
    with pytest.raises(InvalidToken):
        factory.verifier().verify("not-a-jwt")


@pytest.fixture
def whoami(factory: TokenFactory) -> TestClient:
    app = FastAPI()

    @app.get("/whoami")
    def whoami(principal: Annotated[Principal, Depends(require_principal)]) -> dict[str, str]:
        return {"user_id": principal.user_id}

    app.dependency_overrides[get_verifier] = factory.verifier
    return TestClient(app)


def test_require_principal_accepts_valid_bearer(whoami: TestClient, factory: TokenFactory) -> None:
    response = whoami.get("/whoami", headers={"Authorization": f"Bearer {factory.make('user-1', {})}"})
    assert response.status_code == 200
    assert response.json() == {"user_id": "user-1"}


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer junk"}])
def test_require_principal_rejects_missing_or_invalid(whoami: TestClient, headers: dict[str, str]) -> None:
    assert whoami.get("/whoami", headers=headers).status_code == 401
