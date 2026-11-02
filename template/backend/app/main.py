from fastapi import FastAPI

from app import errors
from app.access.routes import router as access_router
from app.billing.routes import router as billing_router
from app.config import BillingModeSettings, FrontendSettings, Settings, get_settings
from app.cors import FrontendCORS
from app.demo.routes import router as demo_router
from app.workspaces.routes import router as workspaces_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings load lazily (per request), so importing needs no env."""
    app = FastAPI(title="api")
    if settings is None:
        BillingModeSettings()  # the one setting checked now: an unsafe mock payment config must not start
    else:
        app.dependency_overrides[get_settings] = lambda: settings
    errors.install(app)  # adds the JSON-500 middleware, so it sits inside CORS (added next)

    def frontend_origin() -> str:
        override = app.dependency_overrides.get(get_settings)
        return override().frontend_url if override else FrontendSettings().frontend_url

    app.add_middleware(FrontendCORS, origin=frontend_origin)
    app.include_router(workspaces_router)
    app.include_router(billing_router)
    app.include_router(access_router)
    app.include_router(demo_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
