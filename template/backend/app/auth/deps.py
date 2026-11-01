from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from app.auth.principal import Principal
from app.auth.tokens import InvalidToken, TokenVerifier
from app.config import Settings, get_settings


@lru_cache
def _default_verifier(issuer: str, project_id: str) -> TokenVerifier:
    return TokenVerifier(issuer, project_id)


def get_verifier(settings: Annotated[Settings, Depends(get_settings)]) -> TokenVerifier:
    return _default_verifier(settings.zitadel_issuer, settings.zitadel_project_id)


def require_principal(
    verifier: Annotated[TokenVerifier, Depends(get_verifier)],
    authorization: Annotated[str | None, Header()] = None,
) -> Principal:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return verifier.verify(authorization.removeprefix("Bearer "))
    except InvalidToken as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token") from exc
