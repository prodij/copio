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


def test_cors_preflight_allows_the_frontend(client: TestClient, settings: Settings) -> None:
    response = client.options("/me/access", headers={
        "Origin": settings.frontend_url,
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Authorization, X-Workspace-Id",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == settings.frontend_url


def test_cors_preflight_ignores_other_origins(client: TestClient) -> None:
    response = client.options("/me/access", headers={
        "Origin": "http://evil.test", "Access-Control-Request-Method": "GET"})
    assert "access-control-allow-origin" not in response.headers


def test_unhandled_error_is_json_500_that_keeps_cors(client: TestClient, settings: Settings) -> None:
    app = client.app

    @app.get("/crash")  # type: ignore[attr-defined]
    def crash() -> None:
        raise RuntimeError("bug")

    response = client.get("/crash", headers={"Origin": settings.frontend_url})
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert response.headers["access-control-allow-origin"] == settings.frontend_url


def test_cors_needs_only_frontend_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DATABASE_URL", "STRIPE_SECRET_KEY", "ZITADEL_PROJECT_ID"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("FRONTEND_URL", "http://app.example")
    get_settings.cache_clear()
    with TestClient(create_app()) as c:
        response = c.get("/health", headers={"Origin": "http://app.example"})
    assert response.headers["access-control-allow-origin"] == "http://app.example"
