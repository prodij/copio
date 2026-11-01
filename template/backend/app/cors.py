from collections.abc import Callable

from starlette.middleware.cors import CORSMiddleware
from starlette.types import ASGIApp, Receive, Scope, Send


class FrontendCORS:
    """CORS for the frontend origin, built on the first request so importing the app needs no env."""

    def __init__(self, app: ASGIApp, origin: Callable[[], str]) -> None:
        self.app = app
        self.origin = origin
        self.inner: ASGIApp | None = None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        if self.inner is None:
            self.inner = CORSMiddleware(
                self.app,
                allow_origins=[self.origin()],
                allow_headers=["Authorization", "Content-Type", "X-Workspace-Id"],
                allow_methods=["*"],
            )
        await self.inner(scope, receive, send)
