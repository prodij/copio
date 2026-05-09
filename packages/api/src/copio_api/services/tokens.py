from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from copio_api.config import get_settings
from copio_api.db import LWAToken


class TokenService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, *, tenant_id: str) -> LWAToken | None:
        result = await self.session.execute(
            select(LWAToken).where(LWAToken.tenant_id == tenant_id)
        )
        return result.scalar_one_or_none()

    async def store(
        self,
        *,
        tenant_id: str,
        seller_id: str,
        refresh_token: str,
    ) -> LWAToken:
        existing = await self.get(tenant_id=tenant_id)
        if existing is not None:
            existing.seller_id = seller_id
            existing.refresh_token = refresh_token
            await self.session.commit()
            await self.session.refresh(existing)
            return existing

        token = LWAToken(
            tenant_id=tenant_id,
            seller_id=seller_id,
            refresh_token=refresh_token,
        )
        self.session.add(token)
        await self.session.commit()
        await self.session.refresh(token)
        return token

    async def get_or_env_fallback(self, *, tenant_id: str) -> tuple[str | None, str | None]:
        """Return (refresh_token, seller_id). Falls back to env for solo founder dev."""
        settings = get_settings()
        existing = await self.get(tenant_id=tenant_id)
        if existing is not None:
            return existing.refresh_token, existing.seller_id
        if settings.lwa_refresh_token and settings.spapi_seller_id:
            return settings.lwa_refresh_token, settings.spapi_seller_id
        return None, None
