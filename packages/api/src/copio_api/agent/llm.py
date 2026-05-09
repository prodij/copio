"""Anthropic SDK direct, with the 4 explicit prompt-cache breakpoints
locked by /plan-eng-review:

  1. Tool definitions
  2. Persona / voice anchor
  3. System prompt (honest-voice)
  4. Memory snapshot (per-tenant)

The dynamic suffix (current question + tool results) is NOT cached.

Eval rig must verify cache_hit_rate >= 0.80; misplaced breakpoints silently
degrade to full-price calls.
"""
from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import (
    RawContentBlockDeltaEvent,
    RawContentBlockStartEvent,
    RawContentBlockStopEvent,
    RawMessageDeltaEvent,
    RawMessageStartEvent,
)

from copio_api.config import Settings, get_settings
from copio_api.logging import get_logger

log = get_logger(__name__)


@dataclass
class CacheStats:
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def hit_rate(self) -> float:
        denom = self.cache_creation_input_tokens + self.cache_read_input_tokens
        return self.cache_read_input_tokens / denom if denom else 0.0


@dataclass
class StreamChunk:
    kind: str  # 'text' | 'tool_use_start' | 'tool_use_input' | 'tool_use_stop' | 'message_stop'
    text: str | None = None
    tool_id: str | None = None
    tool_name: str | None = None
    tool_input_json_delta: str | None = None
    stop_reason: str | None = None


def _cache_block(text: str) -> dict[str, Any]:
    return {
        "type": "text",
        "text": text,
        "cache_control": {"type": "ephemeral"},
    }


def _cached_tools(tools: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mark the LAST tool with cache_control — caches all tool definitions."""
    if not tools:
        return []
    materialized = [dict(t) for t in tools]
    materialized[-1] = {**materialized[-1], "cache_control": {"type": "ephemeral"}}
    return materialized


class LLMClient:
    """Anthropic streaming wrapper with explicit cache breakpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

    def build_system(
        self,
        *,
        voice_doc: str,
        system_prompt: str,
        memory_snapshot: str,
    ) -> list[dict[str, Any]]:
        """3 of the 4 cache breakpoints live in `system` (the 4th is in `tools`).

        Order matters: the cache prefix is matched left-to-right. Putting the
        most-stable content first (voice) and the most-variable last (memory)
        maximizes hit rate as memory grows over time.
        """
        return [
            _cache_block(voice_doc),
            _cache_block(system_prompt),
            _cache_block(memory_snapshot),
        ]

    async def stream(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> AsyncIterator[StreamChunk]:
        async with self._client.messages.stream(
            model=model,
            system=system,
            tools=_cached_tools(tools),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        ) as stream:
            current_tool_id: str | None = None
            current_tool_name: str | None = None
            async for event in stream:
                if isinstance(event, RawContentBlockStartEvent):
                    block = event.content_block
                    if block.type == "tool_use":
                        current_tool_id = block.id
                        current_tool_name = block.name
                        yield StreamChunk(
                            kind="tool_use_start",
                            tool_id=block.id,
                            tool_name=block.name,
                        )
                elif isinstance(event, RawContentBlockDeltaEvent):
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield StreamChunk(kind="text", text=delta.text)
                    elif delta.type == "input_json_delta":
                        yield StreamChunk(
                            kind="tool_use_input",
                            tool_id=current_tool_id,
                            tool_name=current_tool_name,
                            tool_input_json_delta=delta.partial_json,
                        )
                elif isinstance(event, RawContentBlockStopEvent):
                    if current_tool_id is not None:
                        yield StreamChunk(
                            kind="tool_use_stop",
                            tool_id=current_tool_id,
                            tool_name=current_tool_name,
                        )
                        current_tool_id = None
                        current_tool_name = None
                elif isinstance(event, RawMessageDeltaEvent):
                    if event.delta.stop_reason:
                        yield StreamChunk(
                            kind="message_stop",
                            stop_reason=event.delta.stop_reason,
                        )
                elif isinstance(event, RawMessageStartEvent):
                    pass

    @staticmethod
    def usage_from_message(message: Any) -> CacheStats:
        """Pull token + cache stats off the final Anthropic Message."""
        usage = getattr(message, "usage", None)
        if usage is None:
            return CacheStats()
        return CacheStats(
            cache_creation_input_tokens=getattr(usage, "cache_creation_input_tokens", 0) or 0,
            cache_read_input_tokens=getattr(usage, "cache_read_input_tokens", 0) or 0,
            input_tokens=getattr(usage, "input_tokens", 0) or 0,
            output_tokens=getattr(usage, "output_tokens", 0) or 0,
        )

    async def complete_with_tools(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        system: list[dict[str, Any]],
        tools: Sequence[dict[str, Any]],
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> tuple[Any, CacheStats]:
        """Non-streaming completion — used by the eval rig."""
        message = await self._client.messages.create(
            model=model,
            system=system,
            tools=list(_cached_tools(tools)),
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return message, self.usage_from_message(message)
