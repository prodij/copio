import os
from collections.abc import Iterator

import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.auth.deps import get_verifier
from app.config import Settings, get_settings
from app.db import Base, engine_for, get_session
from app.integrations import get_lago, get_zitadel
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient
from app.main import create_app
from tests.auth_helpers import AuthHeaders, TokenFactory
from tests.fakes import fake_lago, fake_zitadel

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


@pytest.fixture(scope="session")
def tokens(settings: Settings) -> TokenFactory:
    return TokenFactory(settings)


@pytest.fixture
def auth(tokens: TokenFactory) -> AuthHeaders:
    def headers(user_id: str, orgs: dict[str, str] | None = None, **claims: object) -> dict[str, str]:
        return {"Authorization": f"Bearer {tokens.make(user_id, orgs or {}, **claims)}"}  # type: ignore[arg-type]

    return headers


@pytest.fixture
def client(db_session: Session, settings: Settings, tokens: TokenFactory) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_session] = lambda: db_session
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_verifier] = tokens.verifier
    app.dependency_overrides[get_zitadel] = lambda: ZitadelClient(
        settings.zitadel_api_url, "t", settings.zitadel_instance_org_id, settings.zitadel_project_id
    )
    app.dependency_overrides[get_lago] = lambda: LagoClient(settings.lago_api_url, "k")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def owner_workspace(client: TestClient, auth: AuthHeaders) -> str:
    """Id of a ready workspace owned by user-1 (its Zitadel org id is the same id)."""
    with respx.mock:
        fake_zitadel(respx.mock)
        fake_lago(respx.mock)
        r = client.post("/workspaces", json={"name": "Acme"}, headers=auth("user-1"))
    assert r.status_code == 201
    return str(r.json()["id"])


@pytest.fixture
def owner_headers(owner_workspace: str, auth: AuthHeaders) -> dict[str, str]:
    return auth("user-1", {owner_workspace: "owner"})
