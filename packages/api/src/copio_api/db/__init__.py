from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from copio_api.config import get_settings
from copio_api.db.models import (
    AuditLog,
    Base,
    Diagnostic,
    DiagnosticState,
    LWAToken,
    MemoryRecord,
    Message,
    Reaction,
    Thread,
)

_settings = get_settings()

engine = create_async_engine(
    _settings.database_url,
    echo=False,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


__all__ = [
    "AuditLog",
    "Base",
    "Diagnostic",
    "DiagnosticState",
    "LWAToken",
    "MemoryRecord",
    "Message",
    "Reaction",
    "SessionLocal",
    "Thread",
    "engine",
    "get_session",
    "session_scope",
]
