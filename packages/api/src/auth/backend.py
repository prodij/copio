"""FastAPI Users authentication backend configuration."""

from uuid import UUID

from fastapi_users import FastAPIUsers
from fastapi_users.authentication import (
    AuthenticationBackend,
    BearerTransport,
    JWTStrategy,
)

from src.config import settings
from src.db.models.user import User
from src.auth.manager import get_user_manager


def get_jwt_strategy() -> JWTStrategy:
    """Create JWT strategy with configured secret and lifetime."""
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.access_token_expire_minutes * 60,
    )


# Bearer token transport (Authorization: Bearer <token>)
bearer_transport = BearerTransport(tokenUrl="/api/v1/auth/login")

# Auth backend combining transport + strategy
auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

# FastAPI Users instance
fastapi_users = FastAPIUsers[User, UUID](
    get_user_manager,
    [auth_backend],
)
