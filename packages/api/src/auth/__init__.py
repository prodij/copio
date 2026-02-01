"""Authentication module using fastapi-users."""

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import get_user_manager
from src.auth.routes import router as auth_router

# Current user dependencies
current_user = fastapi_users.current_user()
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

# Optional current user (returns None instead of raising if not authenticated)
current_user_optional = fastapi_users.current_user(optional=True)
current_active_user_optional = fastapi_users.current_user(active=True, optional=True)

__all__ = [
    "auth_backend",
    "fastapi_users",
    "get_user_manager",
    "auth_router",
    "current_user",
    "current_active_user",
    "current_superuser",
    "current_user_optional",
    "current_active_user_optional",
]
