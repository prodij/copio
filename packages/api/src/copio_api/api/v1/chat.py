from collections.abc import AsyncGenerator
from typing import Annotated

import orjson
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.agent.orchestrator import DiagnosticOrchestrator, StreamEvent
from copio_api.config import Settings, get_settings
from copio_api.db import get_session
from copio_api.logging import get_logger
from copio_api.schemas.chat import ChatRequest
from copio_api.services.threads import ThreadService

router = APIRouter()
log = get_logger(__name__)


@router.post("")
async def chat_stream(
    body: ChatRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    if not body.messages:
        raise HTTPException(status_code=400, detail="messages cannot be empty")

    last_user = next(
        (m for m in reversed(body.messages) if m.role == "user"),
        None,
    )
    if last_user is None:
        raise HTTPException(status_code=400, detail="no user message found")

    threads = ThreadService(session)
    thread, _user_msg = await threads.append_user_message(
        thread_id=body.thread_id,
        tenant_id=settings.founder_tenant_id,
        content=last_user.text,
    )

    orchestrator = DiagnosticOrchestrator(session=session, settings=settings)

    async def event_stream() -> AsyncGenerator[bytes, None]:
        async for event in orchestrator.run(thread_id=thread.id, question=last_user.text):
            yield _format_data_stream_event(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/plain; charset=utf-8",
        headers={
            "x-vercel-ai-data-stream": "v1",
            "cache-control": "no-cache, no-transform",
            "x-thread-id": str(thread.id),
        },
    )


def _format_data_stream_event(event: StreamEvent) -> bytes:
    """
    Encode an orchestrator event in the Vercel AI SDK Data Stream Protocol.

    Text deltas use prefix '0:' followed by a JSON-encoded string (the raw
    delta — not an object). All other events ride the '2:' data channel so
    the client renders them as annotations (sub-states, citations, finish).
    """
    if event.kind == "text":
        text = event.payload.get("value", "")
        return f"0:{orjson.dumps(text).decode()}\n".encode()
    payload = {"type": event.kind, **event.payload}
    return f"2:{orjson.dumps([payload]).decode()}\n".encode()
