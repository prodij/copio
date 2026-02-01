"""API v1 router - aggregates all v1 routes."""

from fastapi import APIRouter

from src.api.v1 import velocity, sync
from src.api.v1 import products
from src.api.v1 import categories
from src.api.v1 import locations
from src.api.v1 import stock_items
from src.api.v1 import stock_movements
from src.api.v1 import vendors
from src.api.v1 import vendor_contacts
from src.api.v1 import vendor_addresses
from src.api.v1 import vendor_documents
from src.api.v1 import vendor_products
from src.api.v1 import channel_listings
from src.api.v1 import purchase_orders
from src.api.v1 import roles
from src.api.v1 import users
from src.api.v1 import permissions
from src.api.v1 import audit_log
from src.auth.routes import router as auth_router

api_router = APIRouter()

# Auth routes
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

# Feature routes (existing)
api_router.include_router(velocity.router, prefix="/velocity", tags=["Velocity"])
api_router.include_router(sync.router, prefix="/sync", tags=["Sync"])

# Inventory routes (migrated from TypeScript)
api_router.include_router(products.router, prefix="/products", tags=["Products"])
api_router.include_router(categories.router, prefix="/categories", tags=["Categories"])
api_router.include_router(locations.router, prefix="/locations", tags=["Locations"])
api_router.include_router(stock_items.router, prefix="/stock-items", tags=["Stock Items"])
api_router.include_router(stock_movements.router, prefix="/stock-movements", tags=["Stock Movements"])

# Vendor routes (migrated from TypeScript)
api_router.include_router(vendors.router, prefix="/vendors", tags=["Vendors"])
api_router.include_router(vendor_contacts.router, prefix="/vendor-contacts", tags=["Vendor Contacts"])
api_router.include_router(vendor_addresses.router, prefix="/vendor-addresses", tags=["Vendor Addresses"])
api_router.include_router(vendor_documents.router, prefix="/vendor-documents", tags=["Vendor Documents"])
api_router.include_router(vendor_products.router, prefix="/vendor-products", tags=["Vendor Products"])

# Channel & Orders routes (migrated from TypeScript)
api_router.include_router(channel_listings.router, prefix="/channel-listings", tags=["Channel Listings"])
api_router.include_router(purchase_orders.router, prefix="/purchase-orders", tags=["Purchase Orders"])

# RBAC routes
api_router.include_router(roles.router, prefix="/roles", tags=["Roles"])
api_router.include_router(permissions.router, prefix="/permissions", tags=["Permissions"])

# Users routes
api_router.include_router(users.router)

# Audit Log routes
api_router.include_router(audit_log.router)
