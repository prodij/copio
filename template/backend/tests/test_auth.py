import base64
import hashlib
import hmac
import json
import time
from typing import Annotated

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.deps import get_verifier, require_principal
from app.auth.principal import Principal
from app.auth.tokens import InvalidToken, TokenVerifier
from app.config import Settings
from app.errors import install
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
    install(app)

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


def _b64(data: dict[str, object]) -> str:
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


def _claims(factory: TokenFactory, **drop: object) -> dict[str, object]:
    claims: dict[str, object] = {
        "iss": factory.settings.zitadel_issuer,
        "sub": "user-1",
        "aud": [factory.settings.zitadel_project_id],
        "exp": int(time.time()) + 300,
    }
    for name in drop:
        del claims[name]
    return claims


def test_token_signed_by_another_key_is_rejected(factory: TokenFactory) -> None:
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    forged = jwt.encode(_claims(factory), other, algorithm="RS256")
    with pytest.raises(InvalidToken):
        factory.verifier().verify(forged)


def test_alg_none_is_rejected(factory: TokenFactory) -> None:
    token = f"{_b64({'alg': 'none', 'typ': 'JWT'})}.{_b64(_claims(factory))}."
    with pytest.raises(InvalidToken):
        factory.verifier().verify(token)


def test_hs256_signed_with_public_key_is_rejected(factory: TokenFactory) -> None:
    public_pem = factory._private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    header = _b64({"alg": "HS256", "typ": "JWT"})
    body = _b64(_claims(factory))
    sig = hmac.new(public_pem, f"{header}.{body}".encode(), hashlib.sha256).digest()
    token = f"{header}.{body}.{base64.urlsafe_b64encode(sig).rstrip(b'=').decode()}"
    with pytest.raises(InvalidToken):
        factory.verifier().verify(token)


@pytest.mark.parametrize("missing", ["sub", "aud", "exp"])
def test_token_missing_required_claim_is_rejected(factory: TokenFactory, missing: str) -> None:
    token = jwt.encode(_claims(factory, **{missing: None}), factory._private, algorithm="RS256")
    with pytest.raises(InvalidToken):
        factory.verifier().verify(token)


@pytest.mark.parametrize("bad", ["owner", ["owner"], 5])
def test_malformed_roles_claim_yields_no_roles(factory: TokenFactory, bad: object) -> None:
    claims_key = f"urn:zitadel:iam:org:project:{factory.settings.zitadel_project_id}:roles"
    token = factory.make("user-1", {}, **{claims_key: bad})
    assert factory.verifier().verify(token).roles_by_org == {}


def test_jwks_unreachable_is_503_naming_zitadel(factory: TokenFactory) -> None:
    class _Down:
        def get_signing_key_from_jwt(self, _token: str) -> jwt.PyJWK:
            raise jwt.PyJWKClientConnectionError("connection refused")

    app = FastAPI()
    install(app)

    @app.get("/whoami")
    def whoami(principal: Annotated[Principal, Depends(require_principal)]) -> dict[str, str]:
        return {"user_id": principal.user_id}

    app.dependency_overrides[get_verifier] = lambda: TokenVerifier(
        factory.settings.zitadel_issuer, factory.settings.zitadel_project_id, jwks_client=_Down()  # type: ignore[arg-type]
    )
    response = TestClient(app).get("/whoami", headers={"Authorization": "Bearer abc.def.ghi"})
    assert response.status_code == 503
    assert "zitadel" in response.json()["detail"]
