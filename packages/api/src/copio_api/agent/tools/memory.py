from __future__ import annotations

from typing import Any

from copio_api.agent.memory import MemoryStore
from copio_api.agent.tools.base import Tool, ToolContext, ToolResult


async def _remember_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    kind = (args.get("kind") or "note").strip()
    body = (args.get("body") or "").strip()
    if not body:
        return ToolResult(content={"error": "empty_body"})
    if kind not in {"preference", "fact", "decision", "note"}:
        kind = "note"
    store = MemoryStore(tenant_id=ctx.tenant_id)
    entry = await store.append(kind=kind, body=body)
    return ToolResult(
        content={
            "ok": True,
            "kind": entry.kind,
            "body": entry.body,
            "created_at": entry.created_at,
        }
    )


async def _recall_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    limit = int(args.get("limit", 50))
    store = MemoryStore(tenant_id=ctx.tenant_id)
    entries = await store.list(limit=limit)
    return ToolResult(
        content={
            "n": len(entries),
            "entries": [
                {"kind": e.kind, "body": e.body, "created_at": e.created_at}
                for e in entries
            ],
        }
    )


MEMORY_TOOLS: list[Tool] = [
    Tool(
        name="remember",
        description=(
            "Persist a CEO preference, decision, or fact to memory so future "
            "diagnostics can reference it. Use when the user states a preference "
            "(\"do not suggest Walmart\"), commits to a decision, or shares a "
            "business fact you want to recall later."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["preference", "fact", "decision", "note"],
                },
                "body": {
                    "type": "string",
                    "description": "Single-sentence memory entry, in your own words.",
                },
            },
            "required": ["body"],
        },
        handler=_remember_handler,
        label="Remember",
    ),
    Tool(
        name="recall",
        description=(
            "Recall the last N memory entries for this account. Use when the user "
            "references prior conversations or asks 'what did I tell you about X?'"
        ),
        input_schema={
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            },
            "required": [],
        },
        handler=_recall_handler,
        label="Recall",
    ),
]
