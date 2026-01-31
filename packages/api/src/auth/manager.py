"""User manager for fastapi-users."""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, Request
from fastapi_users import BaseUserManager, UUIDIDMixin
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.db.models.user import User
from src.db.session import get_session
from src.services.email import (
    send_verification_email,
    send_password_reset_email,
)

logger = logging.getLogger(__name__)


class UserManager(UUIDIDMixin, BaseUserManager[User, UUID]):
    """Custom user manager with tenant-aware operations."""

    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def on_after_register(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Called after successful registration."""
        logger.info(f"User {user.id} registered for tenant {user.tenant_id}")
        
        # If verification is required, send verification email
        if not user.is_verified:
            # Generate verification token
            token = await self.get_verification_token(user)
            base_url = settings.frontend_url if hasattr(settings, 'frontend_url') else "http://localhost:3000"
            verification_url = f"{base_url}/verify-email?token={token}"
            
            await send_verification_email(
                to=user.email,
                first_name=user.first_name,
                verification_url=verification_url,
            )

    async def on_after_login(
        self,
        user: User,
        request: Optional[Request] = None,
        response: Optional[any] = None,
    ) -> None:
        """Called after successful login."""
        logger.info(f"User {user.id} logged in")

    async def on_after_forgot_password(
        self, user: User, token: str, request: Optional[Request] = None
    ) -> None:
        """Called after password reset request."""
        base_url = settings.frontend_url if hasattr(settings, 'frontend_url') else "http://localhost:3000"
        reset_url = f"{base_url}/reset-password?token={token}"
        
        await send_password_reset_email(
            to=user.email,
            first_name=user.first_name,
            reset_url=reset_url,
        )

    async def on_after_reset_password(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Called after successful password reset."""
        logger.info(f"Password reset completed for {user.email}")

    async def on_after_verify(
        self, user: User, request: Optional[Request] = None
    ) -> None:
        """Called after email verification."""
        logger.info(f"Email verified for {user.email}")

    async def get_verification_token(self, user: User) -> str:
        """Generate a verification token for the user."""
        from fastapi_users.jwt import generate_jwt
        
        data = {"sub": str(user.id), "email": user.email, "aud": "fastapi-users:verify"}
        return generate_jwt(data, self.verification_token_secret, 86400)  # 24 hours


async def get_user_db(session: AsyncSession = Depends(get_session)):
    """Get SQLAlchemy user database adapter."""
    from fastapi_users.db import SQLAlchemyUserDatabase
    yield SQLAlchemyUserDatabase(session, User)


async def get_user_manager(user_db=Depends(get_user_db)):
    """Get user manager instance."""
    yield UserManager(user_db)
