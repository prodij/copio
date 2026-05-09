from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.config import Settings, get_settings
from copio_api.db import get_session
from copio_api.integrations.spapi.lwa import LWAOAuthClient
from copio_api.services.tokens import TokenService

router = APIRouter()


@router.get("/lwa/start")
async def lwa_start(
    settings: Annotated[Settings, Depends(get_settings)],
    application_id: str = Query(..., description="Your SP-API application ID"),
    state: str = "copio-phase-1-0",
) -> RedirectResponse:
    if not settings.lwa_client_id:
        raise HTTPException(status_code=500, detail="LWA_CLIENT_ID not configured")

    params = {
        "application_id": application_id,
        "state": state,
        "version": "beta",
    }
    url = f"https://sellercentral.amazon.com/apps/authorize/consent?{urlencode(params)}"
    return RedirectResponse(url=url, status_code=302)


@router.get("/lwa/callback")
async def lwa_callback(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_session)],
    spapi_oauth_code: str = Query(...),
    selling_partner_id: str = Query(...),
    state: str = Query(...),
) -> dict[str, str]:
    if state != "copio-phase-1-0":
        raise HTTPException(status_code=400, detail="state mismatch")

    client = LWAOAuthClient(settings)
    token = await client.exchange_code(spapi_oauth_code)

    tokens = TokenService(session)
    await tokens.store(
        tenant_id=settings.founder_tenant_id,
        seller_id=selling_partner_id,
        refresh_token=token.refresh_token,
    )
    return {
        "status": "ok",
        "selling_partner_id": selling_partner_id,
        "tenant_id": settings.founder_tenant_id,
    }
