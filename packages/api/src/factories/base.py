"""Base factory configuration for async SQLAlchemy."""

from contextvars import ContextVar
from typing import Any, TypeVar

import factory
from sqlalchemy.ext.asyncio import AsyncSession

# Context variable to hold the current session
_session_context: ContextVar[AsyncSession | None] = ContextVar("session", default=None)


def get_session_context() -> ContextVar[AsyncSession | None]:
    """Get the session context variable."""
    return _session_context


def set_session(session: AsyncSession | None) -> None:
    """Set the current session in context."""
    _session_context.set(session)


def get_session() -> AsyncSession:
    """Get the current session from context."""
    session = _session_context.get()
    if session is None:
        raise RuntimeError("No session set in context. Use set_session() first.")
    return session


T = TypeVar("T")


class AsyncSQLAlchemyFactory(factory.Factory):
    """
    Base factory for async SQLAlchemy models.
    
    Usage:
        async with async_session() as session:
            set_session(session)
            product = await ProductFactory.create_async()
            await session.commit()
    """

    class Meta:
        abstract = True

    @classmethod
    def _create(cls, model_class: type[T], *args: Any, **kwargs: Any) -> T:
        """Synchronous create - adds to session but doesn't commit."""
        session = get_session()
        obj = model_class(*args, **kwargs)
        session.add(obj)
        return obj

    @classmethod
    async def create_async(cls, **kwargs: Any) -> Any:
        """Create an instance and add to session."""
        return cls.create(**kwargs)

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> list[Any]:
        """Create multiple instances."""
        return cls.create_batch(size, **kwargs)
