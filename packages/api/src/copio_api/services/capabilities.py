from copio_api.config import Settings
from copio_api.schemas.capability import CapabilityState


def describe_capabilities(settings: Settings) -> list[CapabilityState]:
    has_lwa = bool(settings.lwa_refresh_token and settings.spapi_seller_id)
    spapi_status = "ready" if has_lwa else "reconnect"
    spapi_detail = "Ready" if has_lwa else "Connect Amazon"

    return [
        CapabilityState(
            id="orders",
            label="Orders",
            status=spapi_status,
            detail=spapi_detail,
            reconnect_url=None if has_lwa else "/api/v1/auth/lwa/start",
        ),
        CapabilityState(
            id="fba_inventory",
            label="FBA Inventory",
            status=spapi_status,
            detail=spapi_detail,
            reconnect_url=None if has_lwa else "/api/v1/auth/lwa/start",
        ),
        CapabilityState(
            id="reports",
            label="Reports",
            status=spapi_status,
            detail=spapi_detail,
            reconnect_url=None if has_lwa else "/api/v1/auth/lwa/start",
        ),
    ]
