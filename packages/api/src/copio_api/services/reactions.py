from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.db import Reaction
from copio_api.services.audit import AuditService


class ReactionService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditService(session)

    async def upsert(
        self,
        *,
        message_id: str,
        tenant_id: str,
        emoji: str,
        comment: str | None,
    ) -> Reaction:
        mid = UUID(str(message_id))
        result = await self.session.execute(
            select(Reaction).where(
                Reaction.message_id == mid,
                Reaction.tenant_id == tenant_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            existing.emoji = emoji
            if comment is not None:
                existing.comment = comment
            await self.session.commit()
            await self.session.refresh(existing)
            await self.audit.log(
                tenant_id=tenant_id,
                event_type="reaction.updated",
                payload={"message_id": str(mid), "emoji": emoji, "comment": comment},
            )
            return existing

        record = Reaction(
            message_id=mid,
            tenant_id=tenant_id,
            emoji=emoji,
            comment=comment,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        await self.audit.log(
            tenant_id=tenant_id,
            event_type="reaction.created",
            payload={"message_id": str(mid), "emoji": emoji, "comment": comment},
        )
        return record
