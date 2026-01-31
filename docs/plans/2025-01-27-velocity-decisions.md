# Sales Velocity System — Decision Record

**Date:** 2025-01-27  
**Status:** Approved  
**Context:** Copio multi-marketplace seller ERP

This document captures ALL decisions made during the design session. Reference this to avoid drift.

---

## 1. Core Concept

### What is Sales Velocity?
The rate at which products sell through retail channels. Measured in **units/day**.

### Why Track It?
- **Reorder forecasting** — Know when to replenish
- **Problem detection** — Spot declining listings early
- **Demand planning** — Project revenue and inventory needs
- **AI foundation** — Data for future forecasting models

### Velocity Formula
```
V₁  = units sold yesterday
V₇  = Σ(7-day sales) ÷ 7
V₃₀ = Σ(30-day sales) ÷ 30

Trend = V₇ ÷ V₃₀
  > 1.0 = accelerating
  < 1.0 = slowing
```

---

## 2. Distribution Channels

| Channel Type | Affects Velocity? | Notes |
|--------------|-------------------|-------|
| DTC (Shopify) | ✅ Yes | Owned ecommerce |
| Marketplaces (Amazon, Walmart, TikTok) | ✅ Yes | Third-party platforms |
| Wholesale (B2B) | ❌ No | Separate module, different pricing/terms |
| Disposal | ❌ No | Inventory write-off |
| Return to Vendor | ❌ No | RTV to manufacturer |

**Decision:** Velocity = retail sales only. Wholesale excluded.

---

## 3. Multi-Tenancy

**Decision:** Shared schema with `tenant_id` + Row-Level Security (RLS)

**Why not schema-per-tenant?**
- Simpler operations
- Easier migrations
- Can migrate large tenants to dedicated later

**Implementation:**
- Add `tenant_id` UUID column to all tables
- Enable RLS with policy: `tenant_id = current_setting('app.current_tenant')`
- Set tenant context on each request from JWT claims

---

## 4. Inventory Locations

**Decision:** Location-level inventory + channel-location binding

**Why?**
- A SKU can exist in multiple locations (Warehouse, FBA, 3PL)
- Listings can be fulfilled from specific locations
- MCF (Multi-Channel Fulfillment) means Shopify can ship from FBA

**Structure:**
```
SKU-A: 
  Warehouse-1 = 500 units
  FBA = 200 units
  3PL-East = 150 units

Shopify listing → can fulfill from Warehouse-1 OR FBA (MCF)
Amazon FBA listing → fulfills from FBA only
```

---

## 5. Velocity vs Consumption

**Decision:** Track separately as different signals

| Metric | Question It Answers | Used For |
|--------|---------------------|----------|
| **Velocity** | How fast is this listing selling? | Listing health, marketing decisions |
| **Consumption** | How fast is this location depleting? | Reorder decisions, ops planning |

**Why separate?**
- A Shopify sale fulfilled via MCF (from FBA) should:
  - Credit velocity to the Shopify listing
  - Deduct consumption from the FBA location
- Mixing them conflates sales signal with ops signal

---

## 6. Customer Returns

**Decision:** Gross velocity only. Returns tracked separately.

**Why?**
- Returns are temporally decoupled (return today from sale 45 days ago)
- Netting returns distorts the velocity signal
- Return rate is its own useful metric

**Use returns for:**
- Profitability calculations
- Reorder buffer adjustments
- Listing quality signals (high return rate = problem)

---

## 7. When Does a Sale Count?

**Decision:** Order placed (not shipped, not delivered)

**Why?**
- Velocity should reflect demand signal
- Shipped/delivered adds latency (days)
- Cancellations are typically low (<5%)

**Cancellations:** Tracked separately, don't reduce velocity retroactively.

---

## 8. Velocity Factors

**Decision:** Generalized event overlay system with three scope levels

**What are factors?**
Events that impact velocity, tracked with date ranges for analysis and forecasting.

| Factor Type | Direction | Example |
|-------------|-----------|---------|
| Suppression | ↓ | Price raised to slow sales (low stock, policy hold) |
| Promotion | ↑ | Lightning deal, coupon, % off |
| Advertising | ↑ | PPC campaign, sponsored listing |
| Social/PR | ↑ | Influencer mention, viral post |
| Stockout | ↓ | Out of stock, velocity = 0 |
| Seasonality | ↑↓ | Holiday, Prime Day, back-to-school |
| External | ↑↓ | Competitor OOS, market event |

**Scope levels:**
- **Listing-level:** Factor applies to one specific listing
- **Channel-level:** Factor applies to all listings on a channel (e.g., Prime Day)
- **Tenant-wide:** Factor applies to entire catalog (e.g., brand campaign)

**Why track factors?**
- Exclude anomalies from baseline forecasting
- Attribute velocity changes to causes
- Plan for known future events (seasonality)

---

## 9. Suppression Tracking

**Decision:** Status history log with effective dates

**Why?**
- Need exact date ranges for suppressed periods
- Forecasting should exclude suppressed data
- Full audit trail

**Implementation:**
```
ListingStatusHistory:
  listing_id, status, reason, effective_from, effective_to

Example:
  abc-123, active,     NULL,        2024-01-01, 2024-06-15
  abc-123, suppressed, low_stock,   2024-06-15, 2024-06-22
  abc-123, active,     NULL,        2024-06-22, NULL (current)
```

---

## 10. Bundles

**Decision:** Versioned bundle composition with effective dates

**Why?**
- Bundles change over time ("Starter Kit v2" adds an item)
- Historical velocity → SKU consumption needs composition at time of sale
- Accurate retrospective analysis

**Implementation:**
```
ListingSkuMapping:
  listing_id, product_id, quantity_per_unit, version, effective_from, effective_to
  
Example:
  starter-kit, SKU-A, 2, v1, 2024-01-01, 2024-06-01
  starter-kit, SKU-B, 1, v1, 2024-01-01, 2024-06-01
  starter-kit, SKU-A, 2, v2, 2024-06-01, NULL
  starter-kit, SKU-B, 1, v2, 2024-06-01, NULL
  starter-kit, SKU-C, 1, v2, 2024-06-01, NULL  ← added in v2
```

---

## 11. Time Zones

**Decision:** UTC storage, tenant timezone display

**Implementation:**
- All timestamps stored in UTC
- Tenant configures their timezone
- Velocity daily cutoffs use tenant's local midnight
- UI displays in tenant's timezone

**Why?**
- Consistent storage, no ambiguity
- Most intuitive UX (matches user's business day)
- Avoids channel timezone complexity

---

## 12. Velocity Calculation Frequency

**Decision:** Hourly batch job

**Why hourly (not real-time)?**
- Server load manageable
- V7/V30 don't need real-time updates
- "Today so far" refreshed hourly is acceptable
- Simpler implementation

**Job details:**
- Celery task runs hourly
- Calculates V1, V7, V30 for all listings
- Stores in `listing_velocity` table
- Per-tenant execution

---

## 13. Data Retention

**Decision:** 2-year rolling window + cold archive

**Raw sale events:** 2 years in hot storage (queryable)
**Older data:** Archive to S3/cold storage
**Aggregates:** Keep indefinitely

**Why?**
- 2 years covers most analysis needs
- Keeps primary DB performant
- Can access older data if needed (compliance)

---

## 14. Currency

**Decision:** Multi-currency with USD base

**Storage:**
```
OrderLine:
  unit_price: 29.99
  currency: GBP
  unit_price_base: 38.24  # converted to USD
  fx_rate: 1.275          # rate at transaction time
```

**V1:** USD only, but schema supports multi-currency for future.

---

## 15. Units of Measure

**Decision:** Always "eaches" + pack metadata

**Why?**
- Velocity is always in eaches (what customers buy)
- Inventory counted in eaches (universal)
- Avoids UOM conversion complexity

**Pack metadata for POs:**
```
CatalogItem:
  on_hand_qty: 500     # always eaches
  case_pack: 24        # order in multiples of 24
  min_order_qty: 48    # supplier minimum
```

**Note:** Validate in production, may need adjustment.

---

## 16. Orders vs Sale Events

**Decision:** Orders with line items (both layers)

**Why?**
- Order-level: status tracking, customer returns, revenue reconciliation
- Line-item level: velocity calculation per listing

**Structure:**
```
Order #12345
├── status: shipped
├── Line 1: Listing-A × 2 → sale event
└── Line 2: Listing-B × 1 → sale event
```

---

## 17. Wholesale

**Decision:** Separate future module

**Why wholesale is different:**
- Different pricing (tiered, negotiated)
- Different terms (Net 30/60, credit)
- Different shipping (pallets, freight)
- Different order flow (PO-based, approvals)

**Shared:** Same catalog, same inventory pool
**Separate:** Order tables, pricing, terms

**V1:** No wholesale module. Future addition.

---

## 18. V1 Scope

**V1 = Data Foundation:**
- A. Auto-sync orders from channels ✅
- B. Auto-sync listings from channels ✅
- C. Auto-detect new listings ✅
- D. Auto-calculate velocity (hourly) ✅

**V1 Channels:** Amazon + Shopify only

**V2+ = Actions:**
- Reorder suggestions
- Auto-create POs
- Problem listing detection
- Seasonality adjustments
- Pricing anomaly detection
- AI demand forecasting

---

## 19. V1 Channels

**Decision:** Amazon + Shopify

**Why these two?**
- Amazon = dominant marketplace, complex API (SP-API)
- Shopify = dominant DTC, clean API
- Proves multi-channel model
- Walmart, TikTok = V1.5 or V2

---

## 20. Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Backend | Python + FastAPI | AI ecosystem, proven for data |
| ORM | SQLAlchemy 2.0 | Proven, many examples for AI debugging |
| Migrations | Alembic | Standard for SQLAlchemy |
| Auth | fastapi-users | Self-hosted, no vendor lock-in |
| Background Jobs | Celery + Redis | Battle-tested |
| Database | PostgreSQL + pgvector | RLS, vectors for future AI |
| Frontend | Next.js + shadcn | Already in use |

---

## 21. Architecture

**V1:** Python service alongside existing TypeScript service
**Target:** Unified Python backend

**Why parallel first?**
- No migration risk
- Velocity/AI in Python, existing CRUD in TypeScript
- Migrate TS routes to Python over time

**Shared:**
- Same Postgres database
- Python owns new tables (velocity, factors, sync)
- Single auth system (Python issues tokens, TS validates)

---

## 22. Auth

**Decision:** fastapi-users (self-hosted)

**Why not external (Clerk, Auth0)?**
- No vendor lock-in
- Full control
- Well documented
- Built for FastAPI

**V1 Roles:**
- Admin: Full access, settings, integrations
- Member: View data, can't change settings

---

## 23. Multi-User

**Decision:** Multi-user with roles

**Structure:**
```
Tenant
└── Users (many)
    ├── Admin
    └── Member
```

---

## 24. API Design

**Decision:** REST

**Why not GraphQL?**
- FastAPI excels at REST
- Auto-generated OpenAPI docs
- Simpler to debug, cache, secure
- No clear benefit from GraphQL for this use case

---

## Design Principles

1. **Lean toward most intuitive UX + technical accuracy**
2. **Automate everything possible with full traceability and transparency**
3. **Separate concerns:** Velocity (sales signal) vs Consumption (ops signal)

---

## Anti-Patterns to Avoid

❌ Don't mix velocity with consumption  
❌ Don't net returns against velocity  
❌ Don't count shipped/delivered (use order placed)  
❌ Don't track wholesale in velocity  
❌ Don't store timestamps in local timezone  
❌ Don't use real-time velocity calc (hourly batch is fine)  
❌ Don't build wholesale module in V1  
❌ Don't over-complicate UOM (eaches + metadata)  

---

## Reference: Existing Copio State

**Already exists:**
- Products (with variations)
- ChannelListings (Amazon, Shopify, Walmart, eBay)
- Inventory (Location, StockItem, StockMovement)
- Orders (Order, OrderLine)
- Procurement (Vendor, PurchaseOrder, POLine)
- Vendor CRM (contacts, addresses, documents)

**Being added:**
- Multi-tenancy (tenant_id + RLS)
- Velocity tables
- Velocity factors
- Bundle versioning
- Auth system
- Python API service

---

*Last updated: 2025-01-27*
