import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import Base, engine_for, get_session
from app.main import create_app

TEST_SETTINGS = Settings(
    database_url=os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://app:app@localhost:5432/app_test"),
    frontend_url="http://app.test",
    zitadel_issuer="http://auth.test",
    zitadel_api_url="http://zitadel.test",
    zitadel_project_id="proj-1",
    zitadel_instance_org_id="org-instance",
    zitadel_service_token="test-token",
    lago_api_url="http://lago.test",
    lago_api_key="lago-key",
    lago_webhook_issuer="http://lago.test",
    stripe_secret_key="sk_test_x",
)


@pytest.fixture(scope="session")
def settings() -> Settings:
    return TEST_SETTINGS


@pytest.fixture(scope="session")
def connection(settings: Settings) -> Iterator[Connection]:
    engine = engine_for(settings.database_url)
    with engine.connect() as conn:
        Base.metadata.drop_all(conn)
        Base.metadata.create_all(conn)
        conn.commit()
        yield conn


@pytest.fixture
def db_session(connection: Connection) -> Iterator[Session]:
    trans = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        trans.rollback()


@pytest.fixture
def client(db_session: Session, settings: Settings) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    with TestClient(app) as c:
        yield c
