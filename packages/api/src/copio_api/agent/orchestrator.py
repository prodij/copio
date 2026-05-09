"""Diagnostic orchestrator — Phase 1.0 single-turn agent loop.

State machine (CEO plan):
  QUEUED -> PLANNING -> TOOL_CALLS -> REASONING -> DRAFTING -> STREAMING -> COMPLETE
       \-> FAILED_INTERNAL
       \-> FAILED_NO_DATA
       \-> DEGRADED -> DRAFTING (when some tools fail but enough data exists)

Streams events upward to the API layer. The API layer encodes them in the
Vercel AI SDK Data Stream Protocol so useChat() can render them inline.

Audit-log writes happen at every state transition + every tool call.
"""
from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from anthropic import APIError as AnthropicAPIError
from anthropic import APIStatusError as AnthropicAPIStatusError
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.agent.llm import CacheStats, LLMClient
from copio_api.agent.memory import MemoryStore
from copio_api.agent.prompts import HONEST_VOICE_SYSTEM_PROMPT, VOICE_DOC
from copio_api.agent.tools import find_tool, tool_definitions
from copio_api.agent.tools.base import Citation, ToolContext
from copio_api.config import Settings
from copio_api.db import Diagnostic, DiagnosticState, Thread
from copio_api.integrations.spapi import SPAPIClient
from copio_api.logging import get_logger
from copio_api.services.audit import AuditService
from copio_api.services.threads import ThreadService
from copio_api.services.tokens import TokenService

log = get_logger(__name__)

MAX_AGENT_ITERATIONS = 4  # planning + up to N tool-call rounds
SUB_STATE_MIN_MS = 800  # design spec: each sub-state >=800ms


@dataclass
class StreamEvent:
    kind: str  # 'sub_state' | 'text' | 'citation' | 'reaction_anchor' | 'finish' | 'error' | 'thread'
    payload: dict[str, Any]


@dataclass
class _Run:
    citations: list[Citation] = field(default_factory=list)
    sub_states: list[str] = field(default_factory=list)
    answer_text: str = ""
    cache_stats: CacheStats = field(default_factory=CacheStats)
    degraded: bool = False
    final_state: DiagnosticState = DiagnosticState.STREAMING
    model_used: str = ""
    started_at_monotonic: float = 0.0


class DiagnosticOrchestrator:
    def __init__(
        self,
        *,
        session: AsyncSession,
        settings: Settings,
        llm: LLMClient | None = None,
    ) -> None:
        self.session = session
        self.settings = settings
        self.llm = llm or LLMClient(settings)
        self.audit = AuditService(session)
        self.threads = ThreadService(session)
        self.tokens = TokenService(session)

    async def run(self, *, thread_id: UUID, question: str) -> AsyncIterator[StreamEvent]:
        run = _Run(started_at_monotonic=time.monotonic())
        run.model_used = self.settings.anthropic_default_model

        thread = await self.threads.get(
            thread_id=thread_id, tenant_id=self.settings.founder_tenant_id
        )
        if thread is None:
            yield StreamEvent("error", {"message": "thread not found"})
            return

        yield StreamEvent("thread", {"thread_id": str(thread.id), "title": thread.title})

        await self.audit.log(
            tenant_id=self.settings.founder_tenant_id,
            event_type="diagnostic.queued",
            payload={"thread_id": str(thread.id), "question": question},
        )

        spapi_client = await self._build_spapi_client()

        memory = MemoryStore(tenant_id=self.settings.founder_tenant_id)
        memory_snapshot = await memory.snapshot(limit=50)

        async for ev in self._sub_state(run, "Planning…"):
            yield ev
        await self.audit.log(
            tenant_id=self.settings.founder_tenant_id,
            event_type="diagnostic.planning",
            payload={"thread_id": str(thread.id)},
        )

        ctx = ToolContext(
            tenant_id=self.settings.founder_tenant_id,
            settings=self.settings,
            spapi_client=spapi_client,
        )

        system_blocks = self.llm.build_system(
            voice_doc=VOICE_DOC,
            system_prompt=HONEST_VOICE_SYSTEM_PROMPT,
            memory_snapshot=memory_snapshot,
        )
        anthropic_messages: list[dict[str, Any]] = [
            {"role": "user", "content": question}
        ]
        tools = tool_definitions()

        successful_tool_calls = 0
        failed_tool_calls = 0
        for iteration in range(MAX_AGENT_ITERATIONS):
            answer_chunks: list[str] = []
            tool_uses: list[dict[str, Any]] = []
            current_tool_input: dict[str, str] = {}  # tool_id -> json so far
            current_tool_meta: dict[str, str] = {}  # tool_id -> tool_name
            assistant_blocks: list[dict[str, Any]] = []

            sub_started = False

            stream_iter = self.llm.stream(
                model=run.model_used,
                messages=anthropic_messages,
                system=system_blocks,
                tools=tools,
                max_tokens=2048,
                temperature=0.4,
            )

            chunk_aiter = stream_iter.__aiter__()
            while True:
                try:
                    chunk = await chunk_aiter.__anext__()
                except StopAsyncIteration:
                    break
                except (AnthropicAPIStatusError, AnthropicAPIError, TypeError) as exc:
                    async for ev in self._fail_with_llm_error(
                        run=run,
                        thread=thread,
                        question=question,
                        exc=exc,
                    ):
                        yield ev
                    return
                if chunk.kind == "text":
                    if not sub_started:
                        async for ev in self._sub_state(run, "Reasoning…"):
                            yield ev
                        async for ev in self._sub_state(run, "Drafting…"):
                            yield ev
                        sub_started = True
                    if chunk.text:
                        answer_chunks.append(chunk.text)
                        run.answer_text += chunk.text
                        yield StreamEvent("text", {"value": chunk.text})

                elif chunk.kind == "tool_use_start":
                    if chunk.tool_id and chunk.tool_name:
                        current_tool_input[chunk.tool_id] = ""
                        current_tool_meta[chunk.tool_id] = chunk.tool_name

                elif chunk.kind == "tool_use_input":
                    if chunk.tool_id and chunk.tool_input_json_delta is not None:
                        current_tool_input[chunk.tool_id] += chunk.tool_input_json_delta

                elif chunk.kind == "tool_use_stop":
                    if chunk.tool_id and chunk.tool_id in current_tool_input:
                        raw = current_tool_input.pop(chunk.tool_id) or "{}"
                        name = current_tool_meta.pop(chunk.tool_id, chunk.tool_name or "")
                        try:
                            parsed = json.loads(raw) if raw.strip() else {}
                        except json.JSONDecodeError:
                            parsed = {}
                        tool_uses.append(
                            {"id": chunk.tool_id, "name": name, "input": parsed}
                        )
                        assistant_blocks.append(
                            {
                                "type": "tool_use",
                                "id": chunk.tool_id,
                                "name": name,
                                "input": parsed,
                            }
                        )

                elif chunk.kind == "message_stop":
                    pass

            if "".join(answer_chunks):
                assistant_blocks.insert(
                    0, {"type": "text", "text": "".join(answer_chunks)}
                )

            if not tool_uses:
                break

            async for ev in self._sub_state(run, "Fetching SP-API…"):
                yield ev
            anthropic_messages.append({"role": "assistant", "content": assistant_blocks})
            tool_results_block: list[dict[str, Any]] = []
            for use in tool_uses:
                tool = find_tool(use["name"])
                if tool is None:
                    failed_tool_calls += 1
                    tool_results_block.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": use["id"],
                            "is_error": True,
                            "content": json.dumps(
                                {"error": f"unknown tool: {use['name']}"}
                            ),
                        }
                    )
                    continue
                ts = time.monotonic()
                result = await tool.handler(ctx, use["input"])
                ms = int((time.monotonic() - ts) * 1000)
                await self.audit.log(
                    tenant_id=self.settings.founder_tenant_id,
                    event_type="tool.call",
                    payload={
                        "name": use["name"],
                        "input": use["input"],
                        "ok": not result.degraded,
                        "ms": ms,
                        "note": result.note,
                    },
                )
                if result.degraded:
                    failed_tool_calls += 1
                    run.degraded = True
                else:
                    successful_tool_calls += 1
                for cite in result.citations:
                    run.citations.append(cite)
                    yield StreamEvent("citation", _citation_to_payload(cite))
                tool_results_block.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": use["id"],
                        "is_error": result.degraded,
                        "content": json.dumps(result.content)[:8000],
                    }
                )
            anthropic_messages.append({"role": "user", "content": tool_results_block})

        if successful_tool_calls == 0 and failed_tool_calls > 0 and not run.answer_text:
            run.final_state = DiagnosticState.FAILED_NO_DATA
            run.degraded = True
            err_msg = (
                "I couldn't pull anything useful right now — Amazon SP-API is having "
                "issues, or the account isn't connected yet. Try again in a few minutes "
                "or reconnect the Amazon account from the sidebar."
            )
            run.answer_text = err_msg
            yield StreamEvent("text", {"value": err_msg})
        elif run.degraded:
            run.final_state = DiagnosticState.DEGRADED
        else:
            run.final_state = DiagnosticState.COMPLETE

        latency_ms = int((time.monotonic() - run.started_at_monotonic) * 1000)
        assistant_message = await self.threads.append_assistant_message(
            thread=thread,
            content=run.answer_text,
            citations=[_citation_to_payload(c) for c in run.citations],
            sub_states=run.sub_states,
            state=run.final_state.value,
            degraded=run.degraded,
        )
        diagnostic = Diagnostic(
            message_id=assistant_message.id,
            tenant_id=self.settings.founder_tenant_id,
            question=question,
            final_state=run.final_state.value,
            model_used=run.model_used,
            latency_ms=latency_ms,
            cache_creation_input_tokens=run.cache_stats.cache_creation_input_tokens,
            cache_read_input_tokens=run.cache_stats.cache_read_input_tokens,
            input_tokens=run.cache_stats.input_tokens,
            output_tokens=run.cache_stats.output_tokens,
            cache_hit_rate=run.cache_stats.hit_rate,
        )
        self.session.add(diagnostic)
        await self.session.commit()
        await self.session.refresh(diagnostic)

        await self.audit.log(
            tenant_id=self.settings.founder_tenant_id,
            event_type="diagnostic.complete",
            payload={
                "thread_id": str(thread.id),
                "diagnostic_id": str(diagnostic.id),
                "final_state": run.final_state.value,
                "latency_ms": latency_ms,
                "degraded": run.degraded,
                "successful_tool_calls": successful_tool_calls,
                "failed_tool_calls": failed_tool_calls,
                "cache_hit_rate": run.cache_stats.hit_rate,
            },
            diagnostic_id=diagnostic.id,
        )

        yield StreamEvent(
            "reaction_anchor",
            {"message_id": str(assistant_message.id)},
        )
        yield StreamEvent(
            "finish",
            {
                "state": run.final_state.value,
                "latency_ms": latency_ms,
                "degraded": run.degraded,
                "model": run.model_used,
            },
        )

    async def _sub_state(self, run: _Run, label: str) -> AsyncIterator[StreamEvent]:
        run.sub_states.append(label)
        yield StreamEvent("sub_state", {"label": label})
        await asyncio.sleep(SUB_STATE_MIN_MS / 1000.0)

    async def _fail_with_llm_error(
        self,
        *,
        run: _Run,
        thread: Thread,
        question: str,
        exc: Exception,
    ) -> AsyncIterator[StreamEvent]:
        """Recover from an LLM-side failure (auth missing, rate limit, network)
        by emitting an honest-voice message + a clean finish event so the
        client unwinds correctly. NEVER let the exception escape into the
        SSE stream.
        """
        log.warning("orchestrator.llm_error", error=str(exc)[:200])

        msg_lower = str(exc).lower()
        if "api_key" in msg_lower or "authentication" in msg_lower or isinstance(exc, TypeError):
            text = (
                "I can't reach Anthropic right now. ANTHROPIC_API_KEY is missing "
                "or wrong in the API process environment. Set it in .env and restart "
                "the API server, then ask me again."
            )
        else:
            text = (
                "I hit an error talking to the model. I'll retry next time you "
                "ask. If this keeps happening, check the API logs."
            )

        run.answer_text = text
        run.degraded = True
        run.final_state = DiagnosticState.FAILED_INTERNAL
        yield StreamEvent("text", {"value": text})

        latency_ms = int((time.monotonic() - run.started_at_monotonic) * 1000)
        await self.audit.log(
            tenant_id=self.settings.founder_tenant_id,
            event_type="diagnostic.failed_internal",
            payload={
                "thread_id": str(thread.id),
                "question": question,
                "error": str(exc)[:500],
                "latency_ms": latency_ms,
            },
        )
        message = await self.threads.append_assistant_message(
            thread=thread,
            content=run.answer_text,
            citations=[],
            sub_states=run.sub_states,
            state=run.final_state.value,
            degraded=True,
        )
        yield StreamEvent("reaction_anchor", {"message_id": str(message.id)})
        yield StreamEvent(
            "finish",
            {
                "state": run.final_state.value,
                "latency_ms": latency_ms,
                "degraded": True,
                "model": run.model_used,
            },
        )

    async def _build_spapi_client(self) -> SPAPIClient | None:
        refresh_token, seller_id = await self.tokens.get_or_env_fallback(
            tenant_id=self.settings.founder_tenant_id
        )
        if not (refresh_token and seller_id):
            return None
        return SPAPIClient.from_token(
            refresh_token=refresh_token,
            seller_id=seller_id,
            settings=self.settings,
        )


def _citation_to_payload(c: Citation) -> dict[str, Any]:
    return {
        "id": c.id,
        "label": c.label,
        "source": c.source,
        "detail": c.detail,
        "preview": c.preview,
        "open_in_amazon_url": c.open_in_amazon_url,
    }
