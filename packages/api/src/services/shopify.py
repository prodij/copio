"""Shopify API integration service."""

# TODO: Implement Shopify API connector
# Tasks 3.2.1 - 3.2.4

class ShopifyService:
    """Shopify API integration."""
    
    def __init__(self, credentials: dict):
        self.credentials = credentials
        # TODO: Initialize Shopify client
    
    async def get_install_url(self, shop: str, redirect_uri: str) -> str:
        """Generate OAuth install URL."""
        raise NotImplementedError
    
    async def exchange_code(self, shop: str, code: str) -> dict:
        """Exchange authorization code for access token."""
        raise NotImplementedError
    
    async def verify_webhook(self, data: bytes, hmac_header: str) -> bool:
        """Verify webhook signature."""
        raise NotImplementedError
    
    async def sync_orders(self, since: str | None = None) -> int:
        """Sync orders from Shopify."""
        raise NotImplementedError
    
    async def sync_products(self) -> int:
        """Sync products from Shopify."""
        raise NotImplementedError
    
    async def sync_inventory(self) -> int:
        """Sync inventory from Shopify."""
        raise NotImplementedError
