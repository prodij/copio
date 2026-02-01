# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Copio is a multi-marketplace seller ERP with real-time inventory sync. It's a pnpm monorepo with two active packages:
- **@copio/api** - Python FastAPI backend (port 8000)
- **@copio/web** - Next.js 16 frontend (port 3000)

Note: Legacy TypeScript code exists in `.deprecated/` for reference only.

## Development Commands

```bash
# Start everything (requires Docker for Postgres/Redis/MinIO)
docker compose -f docker-compose.dev.yml up -d
pnpm install
pnpm db:migrate     # Run Alembic migrations

# Start development servers
pnpm dev            # Starts both API and web

# Individual packages
pnpm --filter @copio/api dev
pnpm --filter @copio/web dev

# Other
pnpm build          # Build all packages
pnpm lint           # Lint (web package)
pnpm typecheck      # TypeScript checking
```

## Architecture

### Data Flow
```
Browser → Next.js (3000) → /api/* proxy → Python FastAPI (8000) → PostgreSQL
```

The web package proxies `/api/*` requests to the Python API (configured in `next.config.ts`).

### Product Data Model (Three Perspectives)

Products have three dimensions of data:

```
┌─────────────────────────────────────────────────────────────────┐
│                          PRODUCT                                 │
│  Master product data + customer-facing defaults                 │
│  - name, description, bulletPoints (customer-facing)            │
│  - costPrice, msrp (defaults)                                   │
│  - physical attributes, identifiers (UPC, ASIN, etc.)           │
└─────────────────────────────────────────────────────────────────┘
         │                           │
         ▼                           ▼
┌─────────────────────┐    ┌─────────────────────────────────────┐
│   VENDOR PRODUCT    │    │        CHANNEL LISTING              │
│   (Procurement)     │    │        (Marketplace)                │
│                     │    │                                     │
│ - vendorSku         │    │ - channelSku (ASIN, etc.)          │
│ - unitCost          │    │ - title (override)                 │
│ - minOrderQty       │    │ - description (override)           │
│ - casePackQty       │    │ - price (channel-specific)         │
│ - orderMultiple     │    │ - fulfillmentChannel               │
│ - leadTimeDays      │    │ - bufferStock, maxQuantity         │
│ - isPreferred       │    │ - handlingDays                     │
└─────────────────────┘    └─────────────────────────────────────┘
```

### Database (SQLAlchemy)

Models are in `packages/api/src/db/models/`. Key models:

**Product Catalog:**
- **Product** - Master product with customer-facing defaults
- **ProductImage** - Images with alt text, position
- **ProductAttribute** - Flexible key-value attributes
- **Category** - Hierarchical taxonomy with channel mappings

**Multi-perspective Data:**
- **VendorProduct** - Vendor-specific: SKU, cost, MOQ, case pack, lead time
- **ChannelListing** - Marketplace-specific: title, price, fulfillment settings

**Inventory:**
- **Location** (WAREHOUSE, FBA, THREEPEL, STORE) → **StockItem**
- **StockMovement** (RECEIVE, SHIP, ADJUST, TRANSFER, DAMAGE, COUNT)

**Procurement:**
- **Vendor** → **VendorProduct** → **Product**
- **PurchaseOrder** → **POLine**

**Orders:**
- **Order** → **OrderLine**

### API Routes (Python FastAPI)

All routes use Pydantic for request validation. Pattern: `packages/api/src/api/v1/*.py`

| Route | Purpose |
|-------|---------|
| `/api/v1/products` | Product CRUD + images + attributes |
| `/api/v1/categories` | Category tree management |
| `/api/v1/locations` | Warehouse/location management |
| `/api/v1/stock-items` | Inventory per location |
| `/api/v1/stock-movements` | Inventory audit trail |
| `/api/v1/vendors` | Vendor management |
| `/api/v1/vendor-products` | Vendor-product mappings |
| `/api/v1/channel-listings` | Marketplace listings |
| `/api/v1/purchase-orders` | Purchase order management |
| `/api/v1/velocity` | Sales velocity analytics |
| `/api/v1/sync` | Marketplace sync operations |

### Frontend (web)

- Server Components for data fetching
- Client Components for interactivity
- UI: Radix UI primitives + Tailwind CSS
- Pages: Dashboard, Products, Categories, Locations, Inventory, Vendors, Purchase Orders

### Product Detail Editor

6-tab editor at `/products/[id]`:
- **Basic Info** - Name, brand, manufacturer, pricing
- **Content** - Descriptions, bullet points, SEO
- **Physical** - Weight, dimensions, package dimensions
- **Identifiers** - UPC, EAN, GTIN, ASIN, MPN
- **Compliance** - Country of origin, certifications, hazmat
- **Media** - Images, attributes

## Testing Notes

### Python API
```bash
cd packages/api
pytest
pytest --cov=src --cov-report=html
```

### Type Checking
```bash
# Python
cd packages/api && mypy src

# TypeScript
pnpm typecheck
```

## Future Enhancements

- **Bundles/Combos** - BUNDLE, COMBO product types
- **Amazon Integration** - SP-API integration (in progress)
- **Shopify/Walmart** - Additional marketplace integrations
