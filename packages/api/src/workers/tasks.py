"""Celery tasks for background processing."""

import asyncio
from datetime import datetime

from src.workers.celery_app import celery
from src.db.session import async_session_maker
from src.services.velocity import calculate_all_velocities, calculate_sku_consumption


def run_async(coro):
    """Helper to run async code in sync Celery tasks."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery.task(bind=True, max_retries=3)
def calculate_velocities_task(self):
    """
    Calculate velocities for all tenants.
    
    Runs hourly via Celery beat.
    """
    async def _run():
        async with async_session_maker() as session:
            # TODO: Get all active tenants
            # For now, placeholder
            tenants = []  # await get_active_tenants(session)
            
            total_listings = 0
            total_skus = 0
            
            for tenant in tenants:
                try:
                    listings = await calculate_all_velocities(session, tenant.id)
                    skus = await calculate_sku_consumption(session, tenant.id)
                    total_listings += listings
                    total_skus += skus
                except Exception as e:
                    # Log error but continue with other tenants
                    print(f"Error processing tenant {tenant.id}: {e}")
            
            await session.commit()
            return {
                "tenants_processed": len(tenants),
                "listings_processed": total_listings,
                "skus_processed": total_skus,
                "completed_at": datetime.utcnow().isoformat(),
            }
    
    try:
        return run_async(_run())
    except Exception as exc:
        self.retry(exc=exc, countdown=60)  # Retry after 1 minute


@celery.task(bind=True, max_retries=3)
def sync_channel_task(self, tenant_id: str, channel: str):
    """
    Sync data from a specific channel for a tenant.
    
    Args:
        tenant_id: Tenant UUID string
        channel: Channel name ('amazon' | 'shopify')
    """
    async def _run():
        # TODO: Implement after channel services are ready
        pass
    
    try:
        return run_async(_run())
    except Exception as exc:
        self.retry(exc=exc, countdown=60)
