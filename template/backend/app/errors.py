from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DependencyUnavailable(Exception):
    def __init__(self, dependency: str) -> None:
        super().__init__(dependency)
        self.dependency = dependency


def install(app: FastAPI) -> None:
    @app.exception_handler(DependencyUnavailable)
    async def _unavailable(_: Request, exc: DependencyUnavailable) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": f"{exc.dependency} is unavailable"})
