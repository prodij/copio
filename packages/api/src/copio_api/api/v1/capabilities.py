from typing import Annotated

from fastapi import APIRouter, Depends

from copio_api.config import Settings, get_settings
from copio_api.schemas.capability import CapabilityState
from copio_api.services.capabilities import describe_capabilities

router = APIRouter()


@router.get("", response_model=list[CapabilityState])
async def list_capabilities(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[CapabilityState]:
    return describe_capabilities(settings)
