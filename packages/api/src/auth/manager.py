"""User manager for fastapi-users."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.user import User
from src.db.session import get_session


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """Custom user manager with tenant-aware operations."""

    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Called after successful registration."""
        print(f"User {user.id} registered for tenant {user.tenant_id}")

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[any] = None,
    ) -> None:
        """Called after successful login."""
        print(f"User {user.id} logged in")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Called after password reset request."""
        # TODO: Send password reset email
        print(f"Password reset requested for {user.email}. Token: {token}")

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Called after successful password reset."""
        print(f"Password reset completed for {user.email}")


async def get_user_db(session: AsyncSession = Depends(get_session)):
    """Get SQLAlchemy user database adapter."""
    from fastapi_users.db import SQLAlchemyUserDatabase
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager instance."""
    yield UserManager(user_db)
