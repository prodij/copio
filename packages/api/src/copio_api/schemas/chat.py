from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatPart(BaseModel):
    type: Literal["text"] = "text"
    text: str = ""


class ChatMessageIn(BaseModel):
    """Vercel AI SDK v5 message shape — `role` + `parts[]`."""
    id: str | None = None
    role: Literal["user", "assistant", "system"]
    parts: list[ChatPart] = Field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(p.text for p in self.parts if p.type == "text").strip()


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]
    thread_id: str | None = None

    @field_validator("messages")
    @classmethod
    def must_have_user(cls, v: list[ChatMessageIn]) -> list[ChatMessageIn]:
        if not any(m.role == "user" for m in v):
            raise ValueError("must include at least one user message")
        return v


class CitationOut(BaseModel):
    id: str
    label: str
    source: str
    detail: str | None = None
    preview: str | None = None
    open_in_amazon_url: str | None = None


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    citations: list[CitationOut] | None = None
    sub_states: list[str] | None = None
    state: str | None = None
    degraded: bool = False
    created_at: datetime

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v) -> str:
        return str(v)


class ThreadOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: list[MessageOut]


class ThreadSummary(BaseModel):
    id: str
    title: str
    preview: str | None = None
    updated_at: datetime
