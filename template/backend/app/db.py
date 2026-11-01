from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def engine_for(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def get_session() -> Iterator[Session]:
    with Session(engine_for(get_settings().database_url)) as session:
        yield session
