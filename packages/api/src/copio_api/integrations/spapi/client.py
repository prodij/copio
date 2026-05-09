from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from tenacity import AsyncRetrying, RetryError, stop_after_attempt, wait_exponential

from copio_api.config import Settings, get_settings
from copio_api.integrations.spapi.exceptions import (
    SPAPIAuthExpired,
    SPAPIBadResponse,
    SPAPINotConfigured,
    SPAPIPermissionDenied,
    SPAPIRateLimit,
    SPAPIUpstreamDown,
)
from copio_api.integrations.spapi.lwa import LWAOAuthClient
from copio_api.logging import get_logger

log = get_logger(__name__)


@dataclass
class CacheEntry:
    value: Any
    expires_at: datetime


@dataclass
class SPAPISession:
    refresh_token: str
    seller_id: str
    marketplace_id: str
    region: str = "NA"
    access_token: str | None = None
    access_token_expires_at: datetime | None = None
    cache: dict[str, CacheEntry] = field(default_factory=dict)


class SPAPIClient:
    """Thin SP-API wrapper.

    Phase 1.0 keeps this small and lazy: we lazy-import python-amazon-sp-api
    inside `call` so the rest of the app can run without that dependency wired
    end-to-end (matters for unit tests + the dev server before LWA is configured).

    Caching uses the (tenant, endpoint, params, day) tuple per the CEO plan:
      - Hot endpoints (Orders, FBA): 15 min TTL
      - Cold reports (Brand Analytics, SQP): 24h TTL
    """

    HOT_TTL = timedelta(minutes=15)
    COLD_TTL = timedelta(hours=24)
    HOT_ENDPOINTS = {"orders", "fba_inventory"}

    def __init__(
        self,
        session: SPAPISession,
        *,
        settings: Settings | None = None,
    ) -> None:
        self.session = session
        self.settings = settings or get_settings()
        self._lock = asyncio.Lock()

    @classmethod
    def from_token(
        cls,
        *,
        refresh_token: str,
        seller_id: str,
        settings: Settings | None = None,
    ) -> SPAPIClient:
        cfg = settings or get_settings()
        return cls(
            SPAPISession(
                refresh_token=refresh_token,
                seller_id=seller_id,
                marketplace_id=cfg.spapi_marketplace_id,
                region=cfg.spapi_region,
            ),
            settings=cfg,
        )

    async def _ensure_access_token(self) -> str:
        async with self._lock:
            now = datetime.now(tz=timezone.utc)
            tok = self.session.access_token
            exp = self.session.access_token_expires_at
            if tok and exp and exp > now + timedelta(seconds=30):
                return tok

            client = LWAOAuthClient(self.settings)
            refreshed = await client.refresh(self.session.refresh_token)
            self.session.access_token = refreshed.access_token
            self.session.access_token_expires_at = now + timedelta(
                seconds=refreshed.expires_in
            )
            return refreshed.access_token

    def _cache_key(self, endpoint: str, params: dict[str, Any]) -> str:
        day = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
        ordered = sorted((str(k), str(v)) for k, v in params.items())
        return f"{endpoint}|{ordered}|{day}"

    def _ttl_for(self, endpoint: str) -> timedelta:
        return self.HOT_TTL if endpoint in self.HOT_ENDPOINTS else self.COLD_TTL

    def _cache_get(self, key: str) -> Any | None:
        entry = self.session.cache.get(key)
        if entry is None:
            return None
        if entry.expires_at <= datetime.now(tz=timezone.utc):
            self.session.cache.pop(key, None)
            return None
        return entry.value

    def _cache_set(self, key: str, value: Any, ttl: timedelta) -> None:
        self.session.cache[key] = CacheEntry(
            value=value,
            expires_at=datetime.now(tz=timezone.utc) + ttl,
        )

    async def call(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        *,
        bypass_cache: bool = False,
    ) -> dict[str, Any]:
        params = params or {}
        key = self._cache_key(endpoint, params)
        if not bypass_cache:
            cached = self._cache_get(key)
            if cached is not None:
                return {"endpoint": endpoint, "params": params, "cached": True, "data": cached}

        await self._ensure_access_token()

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                reraise=True,
                retry=_retry_on_rate_limit,
            ):
                with attempt:
                    data = await self._execute(endpoint, params)
        except RetryError as exc:
            inner = exc.last_attempt.exception() if exc.last_attempt else exc
            if isinstance(inner, SPAPIRateLimit):
                raise inner
            raise SPAPIUpstreamDown(
                f"SP-API {endpoint} failed after retries", endpoint=endpoint
            ) from exc

        ttl = self._ttl_for(endpoint)
        self._cache_set(key, data, ttl)
        return {"endpoint": endpoint, "params": params, "cached": False, "data": data}

    async def _execute(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        """Phase 1.0 executor — thin shim that returns a deterministic stub
        when python-amazon-sp-api is not yet configured. The real HTTP call
        is wired here once a working LWA token is present.

        Stubs are clearly labeled so the agent can render an honest-voice
        degraded-data note rather than pretend to have real data.
        """
        if not (self.session.refresh_token and self.session.seller_id):
            raise SPAPINotConfigured(
                "SP-API not configured for this tenant",
                endpoint=endpoint,
            )

        try:
            from sp_api.api import Inventories, Orders, Reports
            from sp_api.base import Marketplaces, SellingApiException
        except ImportError as exc:
            raise SPAPIUpstreamDown(
                "python-amazon-sp-api not installed", endpoint=endpoint
            ) from exc

        credentials = {
            "refresh_token": self.session.refresh_token,
            "lwa_app_id": self.settings.lwa_client_id,
            "lwa_client_secret": self.settings.lwa_client_secret,
        }
        marketplace = getattr(Marketplaces, "US")
        ts = time.monotonic()

        try:
            if endpoint == "orders":
                client = Orders(credentials=credentials, marketplace=marketplace)
                resp = await asyncio.to_thread(
                    client.get_orders,
                    MarketplaceIds=[self.session.marketplace_id],
                    **params,
                )
                payload = resp.payload
            elif endpoint == "fba_inventory":
                client = Inventories(credentials=credentials, marketplace=marketplace)
                resp = await asyncio.to_thread(
                    client.get_inventory_summary_marketplace,
                    marketplaceIds=[self.session.marketplace_id],
                    **params,
                )
                payload = resp.payload
            elif endpoint == "reports":
                client = Reports(credentials=credentials, marketplace=marketplace)
                resp = await asyncio.to_thread(
                    client.get_reports,
                    **params,
                )
                payload = resp.payload
            else:
                raise SPAPIBadResponse(
                    f"unknown SP-API endpoint: {endpoint}", endpoint=endpoint
                )
        except SellingApiException as exc:
            self._raise_named(endpoint, exc)
        log.info(
            "spapi.call",
            endpoint=endpoint,
            ms=int((time.monotonic() - ts) * 1000),
        )
        if not isinstance(payload, dict):
            try:
                payload = dict(payload)
            except (TypeError, ValueError) as exc:
                raise SPAPIBadResponse(
                    f"non-dict payload from {endpoint}", endpoint=endpoint
                ) from exc
        return payload

    @staticmethod
    def _raise_named(endpoint: str, exc: Exception) -> None:
        """Map python-amazon-sp-api errors onto our named exceptions."""
        status = getattr(exc, "status", None) or getattr(exc, "code", None)
        message = str(exc)[:240]
        if status == 429 or "Throttle" in message or "QuotaExceeded" in message:
            raise SPAPIRateLimit(message, endpoint=endpoint, status=429) from exc
        if status in (401, 403):
            raise SPAPIPermissionDenied(message, endpoint=endpoint, status=status) from exc
        if status and status >= 500:
            raise SPAPIUpstreamDown(message, endpoint=endpoint, status=status) from exc
        raise SPAPIBadResponse(message, endpoint=endpoint, status=status) from exc


def _retry_on_rate_limit(retry_state: Any) -> bool:
    exc = retry_state.outcome.exception() if retry_state.outcome else None
    return isinstance(exc, SPAPIRateLimit)
