from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


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


def install(app: FastAPI) -> None:
    @app.exception_handler(DependencyUnavailable)
    async def _unavailable(_: Request, exc: DependencyUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"{exc.dependency} is unavailable"})

    @app.exception_handler(DependencyRejected)
    async def _rejected(_: Request, exc: DependencyRejected) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": f"{exc.dependency} rejected the request: {exc.reason}"})
