"""System settings service for global configuration."""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.system_settings import SystemSettings

logger = logging.getLogger(__name__)

# Simple in-memory cache with TTL
_cache: dict[str, tuple[Any, datetime]] = {}
CACHE_TTL = timedelta(minutes=5)


def _get_cached(key: str) -> Any | None:
    """Get value from cache if not expired."""
    if key in _cache:
        value, expires_at = _cache[key]
        if datetime.utcnow() < expires_at:
            return value
        del _cache[key]
    return None


def _set_cached(key: str, value: Any) -> None:
    """Set value in cache with TTL."""
    _cache[key] = (value, datetime.utcnow() + CACHE_TTL)


def invalidate_cache(key: str | None = None) -> None:
    """Invalidate cache for a specific key or all keys."""
    if key is None:
        _cache.clear()
    elif key in _cache:
        del _cache[key]


async def get_setting(session: AsyncSession, key: str) -> dict | None:
    """
    Get a system setting by key.

    Returns the value dict, or None if setting doesn't exist.
    Uses in-memory cache to avoid repeated DB queries.
    """
    # Check cache first
    cached = _get_cached(key)
    if cached is not None:
        return cached

    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        return None

    # Cache the value
    _set_cached(key, setting.value)
    return setting.value


async def set_setting(
    session: AsyncSession,
    key: str,
    value: dict,
    description: str | None = None,
) -> SystemSettings:
    """
    Set a system setting value.

    Creates the setting if it doesn't exist, updates if it does.
    Invalidates cache on update.
    """
    result = await session.execute(
        select(SystemSettings).where(SystemSettings.key == key)
    )
    setting = result.scalar_one_or_none()

    if setting is None:
        setting = SystemSettings(key=key, value=value, description=description)
        session.add(setting)
    else:
        setting.value = value
        if description is not None:
            setting.description = description

    await session.commit()
    await session.refresh(setting)

    # Invalidate cache
    invalidate_cache(key)

    return setting


async def get_all_settings(session: AsyncSession) -> list[SystemSettings]:
    """Get all system settings."""
    result = await session.execute(
        select(SystemSettings).order_by(SystemSettings.key)
    )
    return list(result.scalars().all())


async def is_email_verification_required(session: AsyncSession) -> bool:
    """
    Check if email verification is required for login.

    This is a convenience function for the most common setting check.
    """
    value = await get_setting(session, "require_email_verification")
    if value is None:
        # Default to True if setting doesn't exist
        return True
    return value.get("enabled", True)
