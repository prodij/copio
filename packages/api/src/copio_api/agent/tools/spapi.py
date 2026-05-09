from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from copio_api.agent.tools.base import Citation, Tool, ToolContext, ToolResult
from copio_api.integrations.spapi import (
    SPAPIAuthExpired,
    SPAPIBadResponse,
    SPAPIPermissionDenied,
    SPAPIRateLimit,
    SPAPIUpstreamDown,
)
from copio_api.integrations.spapi.exceptions import SPAPINotConfigured
from copio_api.logging import get_logger

log = get_logger(__name__)


def _open_in_amazon_orders() -> str:
    return "https://sellercentral.amazon.com/orders-v3"


def _open_in_amazon_inventory() -> str:
    return "https://sellercentral.amazon.com/inventoryplanning/manageinventory"


def _open_in_amazon_reports() -> str:
    return "https://sellercentral.amazon.com/reportcentral"


async def _safe_call(
    ctx: ToolContext,
    *,
    endpoint: str,
    params: dict[str, Any],
    label: str,
    open_in_amazon_url: str,
) -> ToolResult:
    if ctx.spapi_client is None:
        return ToolResult(
            content={
                "error": "spapi_not_connected",
                "message": (
                    "SP-API is not connected for this account. Surface a re-grant "
                    "link to the CEO before claiming any data."
                ),
            },
            degraded=True,
            note="SP-API not connected.",
        )

    try:
        resp = await ctx.spapi_client.call(endpoint, params)
    except SPAPINotConfigured as exc:
        return ToolResult(
            content={"error": "spapi_not_configured", "message": str(exc)},
            degraded=True,
            note="SP-API not configured for this tenant.",
        )
    except SPAPIPermissionDenied as exc:
        return ToolResult(
            content={"error": "permission_denied", "message": str(exc)},
            degraded=True,
            note=f"Re-grant required for {endpoint}.",
        )
    except SPAPIRateLimit as exc:
        return ToolResult(
            content={"error": "rate_limited", "message": str(exc)},
            degraded=True,
            note=f"{endpoint} rate-limited; using last cached snapshot if available.",
        )
    except SPAPIUpstreamDown as exc:
        return ToolResult(
            content={"error": "upstream_down", "message": str(exc)},
            degraded=True,
            note=f"{endpoint} unavailable upstream.",
        )
    except SPAPIBadResponse as exc:
        return ToolResult(
            content={"error": "bad_response", "message": str(exc)},
            degraded=True,
            note=f"{endpoint} returned malformed data.",
        )
    except SPAPIAuthExpired as exc:
        return ToolResult(
            content={"error": "auth_expired", "message": str(exc)},
            degraded=True,
            note="LWA token expired; re-authenticate via the LWA grant link.",
        )

    citation = Citation(
        id=f"{endpoint}:{datetime.now(tz=timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        label=label,
        source=f"SP-API · {endpoint}",
        detail=", ".join(f"{k}={v}" for k, v in params.items()) or None,
        preview=f"cached={resp.get('cached')}",
        open_in_amazon_url=open_in_amazon_url,
    )
    return ToolResult(
        content={
            "endpoint": endpoint,
            "params": params,
            "cached": resp.get("cached", False),
            "data": resp.get("data"),
        },
        citations=[citation],
    )


async def _orders_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    days = int(args.get("days", 30))
    asin = args.get("asin")
    created_after = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
    params: dict[str, Any] = {"CreatedAfter": created_after}
    if asin:
        params["asin"] = asin
    return await _safe_call(
        ctx,
        endpoint="orders",
        params=params,
        label=f"Orders, last {days}d{f' for {asin}' if asin else ''}",
        open_in_amazon_url=_open_in_amazon_orders(),
    )


async def _fba_inventory_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    asin = args.get("asin")
    sku = args.get("sku")
    params: dict[str, Any] = {"granularityType": "Marketplace"}
    if asin:
        params["asin"] = asin
    if sku:
        params["sellerSkus"] = [sku]
    return await _safe_call(
        ctx,
        endpoint="fba_inventory",
        params=params,
        label=f"FBA inventory{f' · {asin or sku}' if (asin or sku) else ''}",
        open_in_amazon_url=_open_in_amazon_inventory(),
    )


async def _reports_handler(ctx: ToolContext, args: dict[str, Any]) -> ToolResult:
    report_type = args.get("report_type", "GET_SALES_AND_TRAFFIC_REPORT")
    days = int(args.get("days", 30))
    params: dict[str, Any] = {
        "reportTypes": [report_type],
        "createdSince": (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat(),
    }
    return await _safe_call(
        ctx,
        endpoint="reports",
        params=params,
        label=f"{report_type}, last {days}d",
        open_in_amazon_url=_open_in_amazon_reports(),
    )


SPAPI_TOOLS: list[Tool] = [
    Tool(
        name="get_orders",
        description=(
            "Fetch Orders for the connected Amazon seller account, optionally "
            "scoped to an ASIN and a recent window. Use to answer questions "
            "about sales velocity, units, channel mix, recent customer activity. "
            "Returns cached data when fresh; otherwise hits SP-API directly."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Look-back window in days. Default 30, max 90.",
                    "minimum": 1,
                    "maximum": 90,
                },
                "asin": {
                    "type": "string",
                    "description": "Optional ASIN filter (e.g. B0C12345AB).",
                },
            },
            "required": [],
        },
        handler=_orders_handler,
        label="Orders",
    ),
    Tool(
        name="get_fba_inventory",
        description=(
            "Fetch FBA inventory snapshot for the connected account. Use to "
            "diagnose stock-out causes, replenishment lead time, restock risk."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "asin": {"type": "string"},
                "sku": {"type": "string"},
            },
            "required": [],
        },
        handler=_fba_inventory_handler,
        label="FBA Inventory",
    ),
    Tool(
        name="get_report",
        description=(
            "Request and return an SP-API report. Use for Brand Analytics, "
            "Sales-and-Traffic, Search Query Performance. Cold reports cache "
            "for 24h. Honest about freshness — if cached data is stale, the "
            "agent must say so in the answer."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": (
                        "SP-API report type id, e.g. GET_SALES_AND_TRAFFIC_REPORT, "
                        "GET_BRAND_ANALYTICS_SEARCH_TERMS_REPORT, "
                        "GET_BRAND_ANALYTICS_SEARCH_QUERY_PERFORMANCE_REPORT."
                    ),
                },
                "days": {
                    "type": "integer",
                    "description": "Look-back window in days. Default 30.",
                    "minimum": 1,
                    "maximum": 365,
                },
            },
            "required": ["report_type"],
        },
        handler=_reports_handler,
        label="Reports",
    ),
]
