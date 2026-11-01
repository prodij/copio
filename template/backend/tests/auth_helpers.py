import time

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

from app.auth.tokens import TokenVerifier
from app.config import Settings


class _StaticJwks:
    def __init__(self, public_key: rsa.RSAPublicKey) -> None:
        self._key = public_key

    def get_signing_key_from_jwt(self, _token: str) -> jwt.PyJWK:
        return jwt.PyJWK.from_dict(jwt.algorithms.RSAAlgorithm.to_jwk(self._key, as_dict=True) | {"alg": "RS256"})


class TokenFactory:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._private = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def make(self, user_id: str, orgs: dict[str, str], email: str = "u@example.com", **overrides: object) -> str:
        roles: dict[str, dict[str, str]] = {}
        for org_id, role in orgs.items():
            roles.setdefault(role, {})[org_id] = f"{org_id}.test"
        claims = {
            "iss": self.settings.zitadel_issuer,
            "sub": user_id,
            "aud": [self.settings.zitadel_project_id],
            "exp": int(time.time()) + 300,
            "email": email,
            f"urn:zitadel:iam:org:project:{self.settings.zitadel_project_id}:roles": roles,
        } | overrides
        return jwt.encode(claims, self._private, algorithm="RS256")

    def verifier(self) -> TokenVerifier:
        return TokenVerifier(
            self.settings.zitadel_issuer,
            self.settings.zitadel_project_id,
            jwks_client=_StaticJwks(self._private.public_key()),  # type: ignore[arg-type]
        )
