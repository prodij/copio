from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.config import Settings, get_settings
from copio_api.db import get_session
from copio_api.schemas.reaction import ReactionIn, ReactionOut
from copio_api.services.reactions import ReactionService

router = APIRouter()


@router.post("", response_model=ReactionOut, status_code=status.HTTP_201_CREATED)
async def upsert_reaction(
    body: ReactionIn,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ReactionOut:
    reactions = ReactionService(session)
    record = await reactions.upsert(
        message_id=body.message_id,
        tenant_id=settings.founder_tenant_id,
        emoji=body.emoji,
        comment=body.comment,
    )
    return ReactionOut.model_validate(record, from_attributes=True)
