from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import Settings, get_settings
from app.integrations.lago import LagoClient
from app.integrations.zitadel import ZitadelClient


@lru_cache
def _zitadel(api_url: str, token: str, instance_org_id: str, project_id: str) -> ZitadelClient:
    return ZitadelClient(api_url, token, instance_org_id, project_id)


@lru_cache
def _lago(api_url: str, api_key: str) -> LagoClient:
    return LagoClient(api_url, api_key)


def get_zitadel(settings: Annotated[Settings, Depends(get_settings)]) -> ZitadelClient:
    return _zitadel(settings.zitadel_api_url, settings.zitadel_service_token,
                    settings.zitadel_instance_org_id, settings.zitadel_project_id)


def get_lago(settings: Annotated[Settings, Depends(get_settings)]) -> LagoClient:
    return _lago(settings.lago_api_url, settings.lago_api_key)
