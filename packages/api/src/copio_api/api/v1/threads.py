from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.config import Settings, get_settings
from copio_api.db import get_session
from copio_api.schemas.chat import MessageOut, ThreadOut, ThreadSummary
from copio_api.services.threads import ThreadService

router = APIRouter()


@router.get("", response_model=list[ThreadSummary])
async def list_threads(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ThreadSummary]:
    threads = ThreadService(session)
    return await threads.list_summaries(tenant_id=settings.founder_tenant_id)


@router.get("/{thread_id}", response_model=ThreadOut)
async def get_thread(
    thread_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ThreadOut:
    threads = ThreadService(session)
    thread = await threads.get(thread_id=thread_id, tenant_id=settings.founder_tenant_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="thread not found")

    messages = await threads.list_messages(thread_id=thread.id)
    return ThreadOut(
        id=str(thread.id),
        title=thread.title,
        created_at=thread.created_at,
        messages=[MessageOut.model_validate(m, from_attributes=True) for m in messages],
    )
