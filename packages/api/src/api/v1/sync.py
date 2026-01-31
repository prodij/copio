"""Sync API endpoints for channel integrations."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
async def sync_status():
    """Get overall sync status for all channels."""
    return {
        "channels": {
            "amazon": {"status": "not_configured", "last_sync": None},
            "shopify": {"status": "not_configured", "last_sync": None},
        },
        "message": "Sync status endpoint - not yet implemented",
    }


@router.get("/logs")
async def sync_logs():
    """Get sync history logs."""
    return {"logs": [], "message": "Sync logs endpoint - not yet implemented"}


@router.post("/trigger/{channel}")
async def trigger_sync(channel: str):
    """Manually trigger a sync for a channel."""
    return {
        "channel": channel,
        "status": "queued",
        "message": "Sync trigger endpoint - not yet implemented",
    }
