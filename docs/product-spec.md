# Copio Product Spec

**Version:** 0.1 (Draft)
**Date:** 2026-01-27

## Vision

Real-time inventory sync + automated procurement for multi-marketplace sellers.

## Stack

- **Backend:** Python (FastAPI)
- **Frontend:** Next.js + React
- **Database:** PostgreSQL
- **Queue:** Redis
- **Integrations:** Amazon SP-API, Walmart, Shopify, eBay

## MVP Scope (Phase 1)

### Core Features

1. **Real-time Inventory Sync**
   - Webhook-based updates (< 100ms)
   - Amazon SP-API integration
   - Shopify integration
   - Single source of truth dashboard

2. **Basic Procurement**
   - Low stock alerts
   - Auto-generate PO drafts
   - Supplier contact management
   - Lead time tracking

3. **Demand Forecasting (Basic)**
   - Historical sales velocity
   - Seasonality detection
   - Reorder point recommendations

### Out of Scope (MVP)
- Walmart integration (Phase 2)
- eBay integration (Phase 2)
- Multi-location routing (Phase 3)
- Margin reporting (Phase 3)
- Mobile app

## Technical Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│                  (Next.js/React)                     │
└─────────────────────────┬───────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────┐
│                    API LAYER                         │
│                    (FastAPI)                         │
└─────────────────────────┬───────────────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│  PostgreSQL │  │    Redis    │  │  Webhook Queue  │
│  (Data)     │  │  (Cache)    │  │  (Events)       │
└─────────────┘  └─────────────┘  └─────────────────┘
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────────┐
│ Amazon API  │  │ Shopify API │  │  Walmart API    │
└─────────────┘  └─────────────┘  └─────────────────┘
```

## Data Model (Core)

```
Product
  - id
  - sku
  - name
  - variants[]
  - supplier_id

Inventory
  - product_id
  - channel_id
  - quantity
  - reserved
  - available
  - updated_at

Channel
  - id
  - type (amazon|shopify|walmart|ebay)
  - credentials
  - sync_status

Supplier
  - id
  - name
  - lead_time_days
  - contact_info

PurchaseOrder
  - id
  - supplier_id
  - status (draft|sent|confirmed|received)
  - line_items[]
  - expected_date
```

## Success Metrics

- Inventory sync latency < 100ms
- Zero oversells in first 30 days
- 80% user activation (connect 1+ channel)
- NPS > 50

## Timeline

- **Week 1-2:** API scaffolding + Amazon SP-API spike
- **Week 3-4:** Core inventory model + sync logic
- **Week 5-6:** Shopify integration + dashboard MVP
- **Week 7-8:** Procurement module + PO generation
- **Week 9-10:** Testing + beta onboarding
- **Week 11-12:** Launch to private beta (100 users)
