# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Copio is a multi-marketplace seller ERP with real-time inventory sync. It's a pnpm monorepo with three packages:
- **@copio/core** - Shared Prisma database models and TypeScript types
- **@copio/inventory-service** - Express.js REST API (port 3002)
- **@copio/web** - Next.js 16 frontend (port 3000)

## Development Commands

```bash
# Start everything (requires Docker for Postgres/Redis)
docker compose -f docker-compose.dev.yml up -d
pnpm install
pnpm db:push        # Push schema to database

# Database
pnpm db:generate    # Generate Prisma client after schema changes
pnpm db:migrate     # Create and run migrations
pnpm db:studio      # Open Prisma Studio GUI

# Testing (inventory-service only)
pnpm --filter @copio/inventory-service test
pnpm --filter @copio/inventory-service test:watch

# Other
pnpm build          # Build all packages
pnpm lint           # Lint (web package)
pnpm typecheck      # TypeScript checking
```

## Architecture

### Data Flow
```
Browser → Next.js (3000) → /api/* proxy → Express API (3002) → PostgreSQL
```

The web package proxies `/api/*` requests to the inventory-service (configured in `next.config.ts`).

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

### Database (Prisma)

Schema is in `packages/core/prisma/schema.prisma`. Key models:

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

### API Routes (inventory-service)

All routes use Zod for request validation. Pattern: `packages/inventory-service/src/routes/*.ts`

| Route | Purpose |
|-------|---------|
| `/products` | Product CRUD + images + attributes |
| `/categories` | Category tree management |
| `/locations` | Warehouse/location management |
| `/stock-items` | Inventory per location |
| `/stock-movements` | Inventory audit trail |
| `/health` | Health check |

### Frontend (web)

- Server Components for data fetching
- Client Components for interactivity
- UI: Radix UI primitives + Tailwind CSS
- Pages: Dashboard, Products (list + detail editor), Locations, Inventory

### Product Detail Editor

6-tab editor at `/products/[id]`:
- **Basic Info** - Name, brand, manufacturer, pricing
- **Content** - Descriptions, bullet points, SEO
- **Physical** - Weight, dimensions, package dimensions
- **Identifiers** - UPC, EAN, GTIN, ASIN, MPN
- **Compliance** - Country of origin, certifications, hazmat
- **Media** - Images, attributes

## Testing Notes

Tests run sequentially (`fileParallelism: false`) to avoid database conflicts. Each test file should clean up its data in `beforeEach`.

## Future Enhancements

- **Bundles/Combos** - BUNDLE, COMBO product types (see ProductType enum comment)
- **Amazon Integration** - Phase 2
- **Shopify/Walmart** - Phase 3
