# Sales Velocity System Design

**Date:** 2025-01-27  
**Status:** Draft  
**Module:** Copio Inventory Analytics

---

## Overview

Add sales velocity tracking and analytics to Copio. This enables demand forecasting, reorder automation, and listing health monitoring.

**Value proposition:** AI-powered automation with full traceability and transparency.

---

## Design Principles

1. **Lean toward most intuitive UX + technical accuracy**
2. **Automate everything possible with full traceability**
3. **Separate concerns:** Velocity (sales signal) vs Consumption (ops signal)

---

## V1 Scope

**Data Foundation:**
- A. Auto-sync orders from channels ✓
- B. Auto-sync listings from channels ✓
- C. Auto-detect new listings ✓
- D. Auto-calculate velocity (hourly) ✓

**V1 Channels:** Amazon + Shopify

**V2+ (future):**
- Reorder suggestions
- Auto-create POs
- Problem listing detection
- Seasonality adjustments
- Pricing anomaly detection
- AI demand forecasting

---

## Key Decisions

### Multi-tenancy
- **Model:** Shared schema with `tenant_id` on every table
- **Isolation:** PostgreSQL Row-Level Security (RLS)
- **Rationale:** Simpler ops, migrate large tenants later if needed

### Inventory & Locations
- **Location-level inventory:** `on_hand_qty` tracked per SKU per location
- **Channel-location binding:** Listings tied to fulfillment sources
- **Supports:** Own warehouse, FBA, 3PL, multi-channel fulfillment (MCF)

### Velocity Definition
- **Scope:** Retail sales only (DTC + Marketplaces)
- **Excluded:** Wholesale (separate future module)
- **Time windows:** 1-day, 7-day, 30-day averages
- **Unit:** units/day (normalized)
- **Granularity:** Per listing, per channel

### Velocity vs Consumption
- **Velocity:** How fast is this listing selling? (sales/marketing signal)
- **Consumption:** How fast is this location depleting? (ops/reorder signal)
- **Tracked independently** — fulfillment source doesn't affect velocity attribution

### Customer Returns
- **Velocity:** Gross sales only (returns don't reduce velocity)
- **Returns:** Tracked separately, factored into profitability and reorder buffer
- **Rationale:** Returns are temporally decoupled from original sales

### When a Sale Counts
- **Trigger:** Order placed (not shipped/delivered)
- **Rationale:** Velocity reflects demand signal
- **Cancellations:** Tracked separately, don't reduce velocity

### Velocity Factors (Overlays)
Generalized event tracking for anything that impacts velocity:

| Factor Type | Direction | Example |
|-------------|-----------|---------|
| Suppression | ↓ slows | Price raised due to low stock |
| Promotion | ↑ boosts | Lightning deal, coupon |
| Advertising | ↑ boosts | PPC campaign, sponsored listing |
| Social/PR | ↑ boosts | Influencer mention, viral post |
| Stockout | ↓ stops | OOS, velocity = 0 during period |
| Seasonality | varies | Holiday, Prime Day |
| External | varies | Competitor OOS, market event |

**Scope levels:**
- Listing-level (specific ASIN promo)
- Channel-level (Prime Day = all Amazon listings)
- Tenant-wide (brand campaign)

**Implementation:** Status history log with effective dates, enabling exclusion/annotation in forecasting.

### Bundles
- **Versioned:** Bundle composition can change over time
- **Tracking:** Version history with effective dates
- **Velocity:** Tracked at listing level
- **Consumption:** Mapped to component SKUs using composition at time of sale

### Time Zones
- **Storage:** UTC always
- **Display:** Tenant's configured timezone
- **Velocity cutoff:** Based on tenant's local midnight

### Velocity Calculation
- **Frequency:** Hourly batch job
- **V₁:** Sales in last 24h (refreshed hourly)
- **V₇:** Σ(7d sales) ÷ 7
- **V₃₀:** Σ(30d sales) ÷ 30
- **Trend:** V₇ / V₃₀ (>1 = accelerating, <1 = slowing)

### Currency
- **Storage:** Multi-currency (original + base amount)
- **Base:** USD (tenant's base currency)
- **V1:** USD only, multi-currency structure for future

### Data Retention
- **Raw sale events:** 2 years queryable
- **Archive:** Cold storage (S3) for older data
- **Aggregates:** Kept indefinitely

### Units of Measure
- **Inventory:** Always in "eaches" (individual units)
- **Pack metadata:** `case_pack`, `min_order_qty` for PO logic
- **Validate in production:** May need adjustment

---

## Data Model Changes

### New Tables

```prisma
// Multi-tenancy
model Tenant {
  id            String   @id @default(uuid())
  name          String
  slug          String   @unique
  timezone      String   @default("America/Los_Angeles")
  baseCurrency  String   @default("USD")
  settings      Json     @default("{}")
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  // All other tables get tenantId foreign key
}

// Listing velocity (pre-calculated, hourly refresh)
model ListingVelocity {
  id            String   @id @default(uuid())
  tenantId      String
  listingId     String   // FK to ChannelListing
  calculatedAt  DateTime
  
  velocity1d    Decimal  @db.Decimal(10, 2)  // units sold in last 24h
  velocity7d    Decimal  @db.Decimal(10, 2)  // avg units/day over 7 days
  velocity30d   Decimal  @db.Decimal(10, 2)  // avg units/day over 30 days
  
  trend7d30d    Decimal? @db.Decimal(5, 2)   // velocity7d / velocity30d
  
  wasSuppressed Boolean  @default(false)     // any suppression during period?
  
  createdAt     DateTime @default(now())
  
  @@unique([listingId, calculatedAt])
  @@index([tenantId, calculatedAt])
}

// SKU consumption rate (aggregated from listing velocity)
model SkuConsumptionRate {
  id            String   @id @default(uuid())
  tenantId      String
  productId     String   // FK to Product (SKU)
  locationId    String?  // FK to Location (optional, for per-location)
  calculatedAt  DateTime
  
  consumption1d   Decimal @db.Decimal(10, 2)
  consumption7d   Decimal @db.Decimal(10, 2)
  consumption30d  Decimal @db.Decimal(10, 2)
  
  daysOfStock     Decimal? @db.Decimal(10, 1)  // on_hand / consumption30d
  reorderUrgency  String?  // 'ok' | 'low' | 'critical' | 'out'
  
  createdAt       DateTime @default(now())
  
  @@unique([productId, locationId, calculatedAt])
  @@index([tenantId, calculatedAt])
}

// Velocity factors (promotions, suppression, campaigns)
model VelocityFactor {
  id            String   @id @default(uuid())
  tenantId      String
  
  // Scope
  scopeType     String   // 'listing' | 'channel' | 'tenant'
  listingId     String?  // if listing-level
  channel       Channel? // if channel-level
  
  // Factor details
  factorType    String   // 'suppression' | 'promotion' | 'advertising' | 'stockout' | 'seasonality' | 'external'
  direction     String   // 'increase' | 'decrease' | 'mixed'
  name          String   // Display name
  description   String?
  
  // Effective period
  effectiveFrom DateTime
  effectiveTo   DateTime?
  
  // Metadata
  metadata      Json     @default("{}")  // Campaign ID, discount %, etc.
  
  createdAt     DateTime @default(now())
  updatedAt     DateTime @updatedAt
  
  @@index([tenantId, effectiveFrom, effectiveTo])
  @@index([listingId])
}

// Listing status history (for suppression tracking)
model ListingStatusHistory {
  id            String   @id @default(uuid())
  tenantId      String
  listingId     String   // FK to ChannelListing
  
  status        ListingStatus
  reason        String?
  
  effectiveFrom DateTime
  effectiveTo   DateTime?
  
  createdBy     String?
  createdAt     DateTime @default(now())
  
  @@index([listingId, effectiveFrom])
}

// Bundle version tracking
model ListingSkuMapping {
  id            String   @id @default(uuid())
  tenantId      String
  listingId     String   // FK to ChannelListing
  productId     String   // FK to Product (component SKU)
  
  quantityPerUnit Int    @default(1)  // How many of this SKU per listing sale
  
  // Versioning
  version       Int      @default(1)
  effectiveFrom DateTime @default(now())
  effectiveTo   DateTime?
  
  createdAt     DateTime @default(now())
  
  @@index([listingId, effectiveFrom, effectiveTo])
  @@index([productId])
}
```

### Modifications to Existing Tables

```prisma
// Add to OrderLine
model OrderLine {
  // ... existing fields ...
  
  // For velocity tracking
  unitPriceCurrency   String   @default("USD")
  unitPriceBase       Decimal  @db.Decimal(10, 2)  // Converted to tenant base currency
  fxRate              Decimal? @db.Decimal(10, 6)  // Exchange rate used
  
  // Cancellation tracking
  cancelledAt         DateTime?
  cancelledQty        Int      @default(0)
}

// Add to ChannelListing (if not already present)
model ChannelListing {
  // ... existing fields ...
  
  // Suppression tracking  
  suppressionReason   String?
  
  // Relations
  velocityRecords     ListingVelocity[]
  statusHistory       ListingStatusHistory[]
  skuMappings         ListingSkuMapping[]
}

// Add tenantId to all relevant tables
// (Product, ChannelListing, Order, Location, StockItem, etc.)
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  FRONTEND (Next.js + shadcn)                                │
│  - Velocity dashboard                                       │
│  - Listing health cards                                     │
│  - Reorder alerts                                           │
└─────────────────────┬───────────────────────────────────────┘
                      │ REST API
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  BACKEND API (Python + FastAPI)                             │
├─────────────────────────────────────────────────────────────┤
│  Channel Sync Service                                       │
│  ├── Amazon SP-API connector                                │
│  ├── Shopify API connector                                  │
│  └── Order/Listing ingestion                                │
├─────────────────────────────────────────────────────────────┤
│  Velocity Service                                           │
│  ├── Hourly velocity calculation job                        │
│  ├── SKU consumption aggregation                            │
│  └── Factor application                                     │
├─────────────────────────────────────────────────────────────┤
│  V2+: AI Services                                           │
│  ├── Demand forecasting                                     │
│  ├── Anomaly detection                                      │
│  └── Reorder optimization                                   │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│  PostgreSQL + pgvector                                      │
│  ├── RLS for multi-tenancy                                  │
│  ├── Velocity tables                                        │
│  └── Vector embeddings (V2+ AI)                             │
├─────────────────────────────────────────────────────────────┤
│  Redis                                                      │
│  ├── Job queue (Celery)                                     │
│  └── Cache                                                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Velocity Calculation Query

```sql
-- Calculate velocity for all listings (hourly job)
WITH daily_sales AS (
  SELECT 
    ol.listing_id,
    DATE(o.placed_at AT TIME ZONE t.timezone) AS sale_date,
    SUM(ol.quantity - ol.cancelled_qty) AS units_sold
  FROM order_lines ol
  JOIN orders o ON ol.order_id = o.id
  JOIN tenants t ON o.tenant_id = t.id
  WHERE o.placed_at >= NOW() - INTERVAL '30 days'
    AND o.tenant_id = :tenant_id
  GROUP BY ol.listing_id, DATE(o.placed_at AT TIME ZONE t.timezone)
)
INSERT INTO listing_velocity (tenant_id, listing_id, calculated_at, velocity_1d, velocity_7d, velocity_30d, trend_7d_30d)
SELECT
  :tenant_id,
  listing_id,
  NOW(),
  COALESCE(SUM(CASE WHEN sale_date = CURRENT_DATE - 1 THEN units_sold END), 0),
  COALESCE(SUM(CASE WHEN sale_date >= CURRENT_DATE - 7 THEN units_sold END), 0) / 7.0,
  COALESCE(SUM(units_sold), 0) / 30.0,
  NULLIF(COALESCE(SUM(CASE WHEN sale_date >= CURRENT_DATE - 7 THEN units_sold END), 0) / 7.0, 0) /
    NULLIF(COALESCE(SUM(units_sold), 0) / 30.0, 0)
FROM daily_sales
GROUP BY listing_id;
```

---

## API Endpoints (V1)

```
GET  /api/v1/velocity/listings                 # List all listings with velocity
GET  /api/v1/velocity/listings/:id             # Single listing velocity detail
GET  /api/v1/velocity/skus                     # SKU consumption rates
GET  /api/v1/velocity/skus/:id                 # Single SKU consumption detail
GET  /api/v1/velocity/dashboard                # Dashboard summary

POST /api/v1/velocity/factors                  # Create velocity factor
GET  /api/v1/velocity/factors                  # List factors
PUT  /api/v1/velocity/factors/:id              # Update factor
DELETE /api/v1/velocity/factors/:id            # Delete factor

POST /api/v1/listings/:id/suppress             # Mark listing as suppressed
POST /api/v1/listings/:id/activate             # Reactivate listing
GET  /api/v1/listings/:id/status-history       # Listing status history
```

---

## Resolved Questions

1. **Prisma vs SQLAlchemy:** SQLAlchemy — proven, more examples for AI debugging

2. **Existing inventory-service:** TypeScript/Express. Keep running for V1, migrate routes to Python over time. Unified Python backend is the target.

3. **Multi-tenancy migration:** Add tenant_id to all tables, assign existing dev data to first tenant, enable RLS.

4. **Auth system:** fastapi-users (self-hosted) — no vendor lock-in, batteries-included.

---

## Implementation Plan

### Architecture Decision
- **V1:** Python FastAPI service alongside existing TypeScript service
- **Target:** Unified Python backend (migrate TS routes over time)
- **Shared:** Same Postgres database, Python owns new tables

### Phase 1: Foundation (Week 1-2)

**1.1 Python Service Scaffold**
```
packages/api/                    # New Python service
├── pyproject.toml
├── alembic/                     # DB migrations
├── src/
│   ├── main.py                  # FastAPI app
│   ├── config.py                # Settings
│   ├── db/
│   │   ├── base.py              # SQLAlchemy setup
│   │   ├── session.py           # Session management
│   │   └── models/              # SQLAlchemy models
│   ├── api/
│   │   ├── deps.py              # Dependencies (auth, tenant)
│   │   └── v1/
│   │       ├── auth.py
│   │       ├── velocity.py
│   │       └── sync.py
│   ├── services/
│   │   ├── velocity.py          # Velocity calculation
│   │   ├── amazon.py            # SP-API connector
│   │   └── shopify.py           # Shopify connector
│   └── workers/
│       └── tasks.py             # Celery tasks
└── tests/
```

**1.2 Multi-Tenancy Migration**
```sql
-- Migration 001: Add tenants
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    timezone VARCHAR(50) DEFAULT 'America/Los_Angeles',
    base_currency VARCHAR(3) DEFAULT 'USD',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Create default tenant
INSERT INTO tenants (id, name, slug) 
VALUES ('00000000-0000-0000-0000-000000000001', 'Default', 'default');

-- Migration 002: Add tenant_id to all tables
ALTER TABLE "Product" ADD COLUMN tenant_id UUID REFERENCES tenants(id);
UPDATE "Product" SET tenant_id = '00000000-0000-0000-0000-000000000001';
ALTER TABLE "Product" ALTER COLUMN tenant_id SET NOT NULL;
-- (repeat for all tables)

-- Migration 003: Enable RLS
ALTER TABLE "Product" ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON "Product"
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
```

**1.3 Auth Setup (fastapi-users)**
- User model with tenant association
- JWT token with tenant_id claim
- Role-based access (admin/member)
- Password reset, email verification (optional for V1)

### Phase 2: Velocity Core (Week 3-4)

**2.1 New Tables (SQLAlchemy models)**
- ListingVelocity
- SkuConsumptionRate  
- VelocityFactor
- ListingStatusHistory
- ListingSkuMapping (versioned bundles)

**2.2 Velocity Calculation Job**
- Celery task: hourly execution
- Per-tenant calculation
- V1, V7, V30 metrics
- Store in listing_velocity table

**2.3 API Endpoints**
- GET /velocity/listings
- GET /velocity/skus
- POST /velocity/factors
- GET /velocity/dashboard

### Phase 3: Channel Sync (Week 5-6)

**3.1 Amazon SP-API**
- OAuth flow for seller authorization
- Orders sync (polling + webhooks)
- Listings sync
- Inventory sync

**3.2 Shopify**
- OAuth app installation
- Orders webhook
- Products sync

### Phase 4: Integration (Week 7-8)

**4.1 API Gateway**
- Route /api/v1/velocity/* → Python
- Route /api/v1/* (rest) → TypeScript
- Unified auth token validation

**4.2 Frontend Dashboard**
- Velocity cards
- Trend charts
- Factor management UI

---

## Tech Stack Summary

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Auth | fastapi-users |
| Background Jobs | Celery + Redis |
| Database | PostgreSQL + pgvector |
| Frontend | Next.js + shadcn (existing) |
| Channel Sync | python-amazon-sp-api, shopify-python-api |

---

## Appendix: Full Decision Log

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| 1 | Inventory locations | Multi-location (A/B/C all possible) | Multi-tenant SaaS |
| 2 | Tenant isolation | Shared schema + RLS | Simpler ops |
| 3 | Location tracking | Location-level + channel binding | MCF support |
| 4 | Velocity attribution | Separate from consumption | Different questions |
| 5 | Customer returns | Gross velocity (A) | Temporal decoupling |
| 6 | Suppression tracking | Status history log (D) | Audit trail |
| 7 | Factor scope | Listing + Channel + Tenant (C) | Flexible |
| 8 | Time zones | UTC storage, tenant TZ display (D) | UX + accuracy |
| 9 | Velocity frequency | Hourly batch (D simplified) | Server load |
| 10 | Data retention | 2-year rolling + archive (B) | Balance |
| 11 | Orders vs events | Orders with line items (C) | Need both layers |
| 12 | When sale counts | Order placed (A) | Demand signal |
| 13 | Currency | Multi-currency with USD base (B) | Future-proof |
| 14 | Wholesale | Separate future module | Different flow |
| 15 | Which direction | Hybrid data ingestion (D) | Automation focus |
| 16 | V1 automations | A, B, C, D (data foundation) | Phased approach |
| 17 | V1 channels | Amazon + Shopify (B) | Prove model |
| 18 | Units of measure | Eaches + pack metadata (C) | Validate in prod |
| 19 | Bundle management | Versioned (B) | Historical accuracy |
| 20 | Stack | Python/FastAPI + Postgres + pgvector | AI future-proof |
| 21 | Frontend | Next.js + shadcn (existing) | Already in use |
| 22 | Multi-user | Roles (C) - Admin/Member start | Needed |
| 23 | API design | REST (A) | FastAPI strength |
| 24 | Starting point | Extending Copio (C) | Existing system |
