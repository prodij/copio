from collections.abc import Iterator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import Settings, get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_session(settings: Settings = Depends(get_settings)) -> Iterator[Session]:  # noqa: B008
    with Session(engine_for(settings.database_url)) as session:
        yield session
