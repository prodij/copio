from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from copio_api.api.router import api_router, inngest_router
from copio_api.config import get_settings
from copio_api.logging import configure_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log = get_logger(__name__)
    settings = get_settings()
    log.info("copio.startup", env=settings.app_env, port=settings.api_port)
    yield
    log.info("copio.shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Copio API",
        version="0.1.0",
        description="Diagnostic agent for Amazon-native CEOs (Phase 1.0).",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["x-vercel-ai-data-stream"],
    )

    app.include_router(api_router)
    app.include_router(inngest_router)
    return app


app = create_app()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}
