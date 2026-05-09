from copio_api.agent.tools.base import Tool, ToolContext, ToolResult
from copio_api.agent.tools.math import MATH_TOOLS
from copio_api.agent.tools.memory import MEMORY_TOOLS
from copio_api.agent.tools.spapi import SPAPI_TOOLS

ALL_TOOLS: list[Tool] = [*SPAPI_TOOLS, *MATH_TOOLS, *MEMORY_TOOLS]


def tool_definitions() -> list[dict]:
    """Anthropic tool definitions in the order the agent sees them.

    The order matters for prompt caching — keep this stable across requests
    so the cached tool block stays valid.
    """
    return [t.to_anthropic() for t in ALL_TOOLS]


def find_tool(name: str) -> Tool | None:
    return next((t for t in ALL_TOOLS if t.name == name), None)


__all__ = [
    "ALL_TOOLS",
    "Tool",
    "ToolContext",
    "ToolResult",
    "find_tool",
    "tool_definitions",
]
