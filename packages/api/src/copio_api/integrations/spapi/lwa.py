from dataclasses import dataclass

import httpx

from copio_api.config import Settings
from copio_api.integrations.spapi.exceptions import SPAPIAuthExpired, SPAPIUpstreamDown

LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"


@dataclass
class LWAToken:
    access_token: str
    refresh_token: str
    expires_in: int


class LWAOAuthClient:
    """Login With Amazon OAuth helper.

    Phase 1.0 single-tenant: redirect_uri is the founder's localhost callback.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def exchange_code(self, oauth_code: str) -> LWAToken:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                LWA_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": oauth_code,
                    "client_id": self.settings.lwa_client_id,
                    "client_secret": self.settings.lwa_client_secret,
                },
            )
        if r.status_code >= 500:
            raise SPAPIUpstreamDown(
                f"LWA token exchange failed: {r.status_code}", status=r.status_code
            )
        if r.status_code >= 400:
            raise SPAPIAuthExpired(
                f"LWA refused authorization code: {r.text[:200]}", status=r.status_code
            )
        data = r.json()
        return LWAToken(
            access_token=data["access_token"],
            refresh_token=data["refresh_token"],
            expires_in=int(data.get("expires_in", 3600)),
        )

    async def refresh(self, refresh_token: str) -> LWAToken:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(
                LWA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.settings.lwa_client_id,
                    "client_secret": self.settings.lwa_client_secret,
                },
            )
        if r.status_code >= 500:
            raise SPAPIUpstreamDown(
                f"LWA refresh failed: {r.status_code}", status=r.status_code
            )
        if r.status_code >= 400:
            raise SPAPIAuthExpired(
                f"LWA refused refresh token: {r.text[:200]}", status=r.status_code
            )
        data = r.json()
        return LWAToken(
            access_token=data["access_token"],
            refresh_token=refresh_token,
            expires_in=int(data.get("expires_in", 3600)),
        )
