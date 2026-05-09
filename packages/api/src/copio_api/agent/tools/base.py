from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from copio_api.config import Settings


@dataclass
class Citation:
    id: str
    label: str
    source: str
    detail: str | None = None
    preview: str | None = None
    open_in_amazon_url: str | None = None


@dataclass
class ToolContext:
    tenant_id: str
    settings: Settings
    spapi_client: Any | None = None  # SPAPIClient — typed loosely to avoid import cycle


@dataclass
class ToolResult:
    content: dict[str, Any]
    citations: list[Citation] = field(default_factory=list)
    degraded: bool = False
    note: str | None = None


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[ToolContext, dict[str, Any]], Awaitable[ToolResult]]
    label: str

    def to_anthropic(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }
