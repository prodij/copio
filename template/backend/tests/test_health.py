from fastapi.testclient import TestClient

from app.errors import DependencyUnavailable


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
