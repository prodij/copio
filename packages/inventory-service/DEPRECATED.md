# ⚠️ DEPRECATED - TypeScript Inventory Service

This TypeScript-based inventory service has been **deprecated** in favor of the unified Python API.

## Migration Status

All routes from this service have been migrated to the Python API in `packages/api/`:

| TypeScript Route | Python Router |
|------------------|---------------|
| products.ts | api/v1/products.py |
| categories.ts | api/v1/categories.py |
| locations.ts | api/v1/locations.py |
| stock-items.ts | api/v1/stock_items.py |
| stock-movements.ts | api/v1/stock_movements.py |
| vendors.ts | api/v1/vendors.py |
| vendor-contacts.ts | api/v1/vendor_contacts.py |
| vendor-addresses.ts | api/v1/vendor_addresses.py |
| vendor-documents.ts | api/v1/vendor_documents.py |
| vendor-products.ts | api/v1/vendor_products.py |
| purchase-orders.ts | api/v1/purchase_orders.py |
| channel-listings.ts | api/v1/channel_listings.py |

## Using the Python API

The Python API runs on port 8000 (or configured port) and provides:
- Same functionality as this TypeScript service
- Authentication and tenant isolation
- Email notifications
- Better async performance with SQLAlchemy

## Switching Services

Update your frontend/clients to point to the Python API:
- Old: `http://localhost:3002/api/v1/...`
- New: `http://localhost:8000/api/v1/...`

## Why Migrate?

1. **Single Backend**: Auth, sync, velocity, and inventory in one service
2. **Better Type Safety**: Pydantic schemas with full validation
3. **Async Performance**: Native async with SQLAlchemy
4. **Simpler Deployment**: One service to deploy and maintain

## This Code

This TypeScript code is preserved for reference but should not be used for new development. It will be removed in a future cleanup.

**Date Deprecated**: 2025-01-30
