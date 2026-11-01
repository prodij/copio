import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy import Connection, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session
from app.errors import DependencyUnavailable
from app.main import create_app


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_dependency_unavailable_is_503(client: TestClient) -> None:
    app = client.app

    @app.get("/boom")  # type: ignore[attr-defined]
    def boom() -> None:
        raise DependencyUnavailable("Lago")

    response = client.get("/boom")
    assert response.status_code == 503
    assert response.json() == {"detail": "Lago is unavailable"}


def test_injected_settings_reach_get_session(
    settings: Settings, connection: Connection, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("DATABASE_URL", "STRIPE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    app = create_app(settings)

    @app.get("/db-ping")
    def db_ping(session: Session = Depends(get_session)) -> dict[str, int]:  # noqa: B008
        return {"one": session.execute(text("select 1")).scalar_one()}

    with TestClient(app) as c:
        assert c.get("/db-ping").json() == {"one": 1}
