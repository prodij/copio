import importlib
from typing import Any


def run(name: str, event: dict[str, Any]) -> dict[str, Any]:
    module = importlib.import_module(f"jobs.handlers.{name}")
    result: dict[str, Any] = module.handler(event, None)
    return result
