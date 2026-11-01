import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)


class DependencyUnavailable(Exception):
    def __init__(self, dependency: str) -> None:
        super().__init__(dependency)
        self.dependency = dependency


class DependencyRejected(Exception):
    """A dependency answered 4xx to a request we built: our bug or its config, not a retry case."""

    def __init__(self, dependency: str, reason: str) -> None:
        super().__init__(f"{dependency}: {reason}")
        self.dependency = dependency
        self.reason = reason


class JsonServerErrors:
    """Unhandled exceptions become a JSON 500 here, inside the CORS middleware, so the browser can
    read the error instead of reporting a CORS "network error". Starlette's own 500 handler sits
    outside every middleware."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception:
            log.exception("Unhandled error on %s %s", scope.get("method"), scope.get("path"))
            if started:
                raise
            await JSONResponse({"detail": "Internal Server Error"}, status_code=500)(scope, receive, send)


def install(app: FastAPI) -> None:
    app.add_middleware(JsonServerErrors)

    @app.exception_handler(DependencyUnavailable)
    async def _unavailable(_: Request, exc: DependencyUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"{exc.dependency} is unavailable"})

    @app.exception_handler(DependencyRejected)
    async def _rejected(_: Request, exc: DependencyRejected) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": f"{exc.dependency} rejected the request: {exc.reason}"})
