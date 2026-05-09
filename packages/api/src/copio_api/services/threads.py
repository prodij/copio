from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.db import Message, Thread
from copio_api.schemas.chat import ThreadSummary


def _title_from_question(question: str) -> str:
    q = " ".join(question.strip().split())
    return q[:60].rstrip(",.;:") if len(q) > 60 else q


class ThreadService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, thread_id: str | UUID, tenant_id: str) -> Thread | None:
        tid = UUID(str(thread_id))
        result = await self.session.execute(
            select(Thread).where(Thread.id == tid, Thread.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def list_summaries(self, *, tenant_id: str) -> list[ThreadSummary]:
        result = await self.session.execute(
            select(Thread).where(Thread.tenant_id == tenant_id).order_by(desc(Thread.updated_at))
        )
        threads = result.scalars().all()
        summaries: list[ThreadSummary] = []
        for t in threads:
            preview = await self._first_message_preview(t.id)
            summaries.append(
                ThreadSummary(
                    id=str(t.id),
                    title=t.title,
                    preview=preview,
                    updated_at=t.updated_at,
                )
            )
        return summaries

    async def list_messages(self, *, thread_id: UUID) -> Sequence[Message]:
        result = await self.session.execute(
            select(Message).where(Message.thread_id == thread_id).order_by(Message.created_at)
        )
        return result.scalars().all()

    async def _first_message_preview(self, thread_id: UUID) -> str | None:
        result = await self.session.execute(
            select(Message)
            .where(Message.thread_id == thread_id, Message.role == "user")
            .order_by(Message.created_at)
            .limit(1)
        )
        msg = result.scalar_one_or_none()
        if msg is None:
            return None
        text = " ".join(msg.content.strip().split())
        return text[:80] if len(text) > 80 else text

    async def append_user_message(
        self,
        *,
        thread_id: str | None,
        tenant_id: str,
        content: str,
    ) -> tuple[Thread, Message]:
        if thread_id:
            existing = await self.get(thread_id=thread_id, tenant_id=tenant_id)
            if existing is None:
                thread = await self._create(tenant_id=tenant_id, content=content)
            else:
                thread = existing
                thread.updated_at = datetime.now(tz=timezone.utc)
        else:
            thread = await self._create(tenant_id=tenant_id, content=content)

        message = Message(
            thread_id=thread.id,
            tenant_id=tenant_id,
            role="user",
            content=content,
        )
        self.session.add(message)
        await self.session.commit()
        await self.session.refresh(thread)
        await self.session.refresh(message)
        return thread, message

    async def append_assistant_message(
        self,
        *,
        thread: Thread,
        content: str,
        citations: list[dict] | None = None,
        sub_states: list[str] | None = None,
        state: str,
        degraded: bool = False,
    ) -> Message:
        message = Message(
            thread_id=thread.id,
            tenant_id=thread.tenant_id,
            role="assistant",
            content=content,
            citations=citations,
            sub_states=sub_states,
            state=state,
            degraded=degraded,
        )
        self.session.add(message)
        thread.updated_at = datetime.now(tz=timezone.utc)
        await self.session.commit()
        await self.session.refresh(message)
        return message

    async def _create(self, *, tenant_id: str, content: str) -> Thread:
        thread = Thread(tenant_id=tenant_id, title=_title_from_question(content))
        self.session.add(thread)
        await self.session.flush()
        return thread
