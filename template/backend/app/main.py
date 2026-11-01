from fastapi import FastAPI

from app import errors
from app.billing.routes import router as billing_router
from app.config import Settings, get_settings
from app.workspaces.routes import router as workspaces_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings load lazily (per request), so importing needs no env."""
    app = FastAPI(title="api")
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    errors.install(app)
    app.include_router(workspaces_router)
    app.include_router(billing_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
