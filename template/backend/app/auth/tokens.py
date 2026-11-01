from typing import Any

import jwt

from app.auth.principal import Principal
from app.errors import DependencyUnavailable

ROLE_RANK = {"member": 1, "owner": 2}


class InvalidToken(Exception):
    pass


class TokenVerifier:
    def __init__(self, issuer: str, project_id: str, jwks_client: jwt.PyJWKClient | None = None) -> None:
        self.issuer = issuer
        self.project_id = project_id
        self.jwks = jwks_client or jwt.PyJWKClient(f"{issuer}/oauth/v2/keys", cache_keys=True)

    def verify(self, token: str) -> Principal:
        try:
            key = self.jwks.get_signing_key_from_jwt(token)
            claims: dict[str, Any] = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.project_id,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except jwt.PyJWKClientConnectionError as exc:
            raise DependencyUnavailable("zitadel") from exc
        except (jwt.PyJWTError, ValueError) as exc:
            raise InvalidToken(str(exc)) from exc
        return Principal(
            user_id=str(claims["sub"]),
            email=claims.get("email"),
            roles_by_org=self._roles(claims),
        )

    def _roles(self, claims: dict[str, Any]) -> dict[str, str]:
        raw = claims.get(f"urn:zitadel:iam:org:project:{self.project_id}:roles")
        if not isinstance(raw, dict):
            return {}
        result: dict[str, str] = {}
        for role, orgs in raw.items():
            if role not in ROLE_RANK or not isinstance(orgs, dict):
                continue
            for org_id in orgs:
                if ROLE_RANK[role] > ROLE_RANK.get(result.get(org_id, ""), 0):
                    result[org_id] = role
        return result
