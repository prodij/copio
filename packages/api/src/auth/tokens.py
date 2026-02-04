"""Token generation and validation."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from jose import jwt, JWTError
from passlib.hash import argon2

from src.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: UUID, tenant_id: UUID) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    """Decode and validate access token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def create_refresh_token() -> tuple[str, str]:
    """Create refresh token. Returns (raw_token, hashed_token)."""
    raw_token = secrets.token_urlsafe(32)
    hashed = argon2.hash(raw_token)
    return raw_token, hashed


def verify_refresh_token(raw_token: str, hashed: str) -> bool:
    """Verify a refresh token against its hash."""
    return argon2.verify(raw_token, hashed)


def get_refresh_token_expiry() -> datetime:
    """Get expiry datetime for a new refresh token."""
    return datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
