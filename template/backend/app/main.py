from fastapi import FastAPI

from app import errors
from app.access.routes import router as access_router
from app.billing.routes import router as billing_router
from app.config import Settings, get_settings
from app.cors import FrontendCORS
from app.demo.routes import router as demo_router
from app.workspaces.routes import router as workspaces_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings load lazily (per request), so importing needs no env."""
    app = FastAPI(title="api")
    if settings is not None:
        app.dependency_overrides[get_settings] = lambda: settings
    errors.install(app)
    app.add_middleware(
        FrontendCORS, settings=lambda: app.dependency_overrides.get(get_settings, get_settings)()
    )
    app.include_router(workspaces_router)
    app.include_router(billing_router)
    app.include_router(access_router)
    app.include_router(demo_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
