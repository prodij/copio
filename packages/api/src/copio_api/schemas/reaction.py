from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator

ALLOWED_EMOJIS = {"👍", "👎", "🎯", "❓", "🔁"}


class ReactionIn(BaseModel):
    message_id: str
    emoji: str
    comment: str | None = None

    @field_validator("emoji")
    @classmethod
    def must_be_allowed(cls, v: str) -> str:
        if v not in ALLOWED_EMOJIS:
            raise ValueError(f"emoji must be one of {sorted(ALLOWED_EMOJIS)}")
        return v


class ReactionOut(BaseModel):
    id: str
    message_id: str
    emoji: str
    comment: str | None = None
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "message_id", mode="before")
    @classmethod
    def coerce(cls, v) -> str:
        return str(v)
