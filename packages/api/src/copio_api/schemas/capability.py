from typing import Literal

from pydantic import BaseModel

CapabilityStatus = Literal["ready", "syncing", "reconnect", "unavailable"]


class CapabilityState(BaseModel):
    id: str
    label: str
    status: CapabilityStatus
    detail: str | None = None
    reconnect_url: str | None = None
