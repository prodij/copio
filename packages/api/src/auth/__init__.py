"""Authentication module using fastapi-users."""

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import get_user_manager
from src.auth.routes import router as auth_router

# Current user dependencies
current_user = fastapi_users.current_user()
current_active_user = fastapi_users.current_user(active=True)
current_superuser = fastapi_users.current_user(active=True, superuser=True)

__all__ = [
    "auth_backend",
    "fastapi_users",
    "get_user_manager",
    "auth_router",
    "current_user",
    "current_active_user",
    "current_superuser",
]
