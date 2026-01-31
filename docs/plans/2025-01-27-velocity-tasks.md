# Sales Velocity System — Task Breakdown

**Reference:** [Decision Record](./2025-01-27-velocity-decisions.md)

---

## Phase 1: Foundation (Week 1-2)

### 1.1 Python Service Scaffold

**Task 1.1.1: Initialize Python Package**
- [ ] Create `packages/api/` directory
- [ ] Set up `pyproject.toml` with dependencies:
  - fastapi
  - uvicorn
  - sqlalchemy[asyncio]
  - alembic
  - fastapi-users[sqlalchemy]
  - celery[redis]
  - httpx (for channel APIs)
  - python-jose (JWT)
  - passlib[argon2]
  - pydantic-settings
- [ ] Create virtual environment setup instructions
- [ ] Add to pnpm workspace (or separate Python tooling)

**Acceptance:** `uvicorn src.main:app` starts successfully

---

**Task 1.1.2: Project Structure**
- [ ] Create directory structure:
```
packages/api/
├── pyproject.toml
├── alembic.ini
├── alembic/
│   └── versions/
├── src/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings (pydantic-settings)
│   ├── db/
│   │   ├── __init__.py
│   │   ├── base.py          # SQLAlchemy Base
│   │   ├── session.py       # Engine, SessionLocal
│   │   └── models/
│   │       ├── __init__.py
│   │       ├── tenant.py
│   │       ├── user.py
│   │       ├── velocity.py
│   │       └── sync.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── deps.py          # Dependency injection
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py
│   │       ├── auth.py
│   │       ├── tenants.py
│   │       ├── velocity.py
│   │       └── sync.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── velocity.py
│   │   ├── amazon.py
│   │   └── shopify.py
│   ├── schemas/             # Pydantic models
│   │   ├── __init__.py
│   │   ├── velocity.py
│   │   └── sync.py
│   └── workers/
│       ├── __init__.py
│       ├── celery_app.py
│       └── tasks.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    └── test_velocity.py
```

**Acceptance:** Clean import structure, no circular dependencies

---

**Task 1.1.3: Configuration & Environment**
- [ ] Create `src/config.py` with pydantic-settings:
  - DATABASE_URL
  - REDIS_URL
  - SECRET_KEY
  - AMAZON_CLIENT_ID, AMAZON_CLIENT_SECRET
  - SHOPIFY_API_KEY, SHOPIFY_API_SECRET
  - Environment (dev/staging/prod)
- [ ] Create `.env.example`
- [ ] Add to docker-compose.dev.yml (Python service + Redis)

**Acceptance:** Config loads from environment, validates required fields

---

**Task 1.1.4: Database Connection**
- [ ] Set up SQLAlchemy async engine in `db/session.py`
- [ ] Create Base class in `db/base.py`
- [ ] Create session dependency for FastAPI
- [ ] Test connection to existing Postgres

**Acceptance:** Can query existing `Product` table from Python

---

**Task 1.1.5: Alembic Migrations Setup**
- [ ] Initialize Alembic: `alembic init alembic`
- [ ] Configure `alembic.ini` and `env.py` for async
- [ ] Point to same database as Prisma
- [ ] Create naming convention matching Prisma's

**Acceptance:** `alembic revision --autogenerate` works

---

### 1.2 Multi-Tenancy Migration

**Task 1.2.1: Tenant Model & Migration**
- [ ] Create `Tenant` SQLAlchemy model:
  ```python
  class Tenant(Base):
      id: UUID
      name: str
      slug: str (unique)
      timezone: str = "America/Los_Angeles"
      base_currency: str = "USD"
      settings: dict = {}
      created_at: datetime
      updated_at: datetime
  ```
- [ ] Create Alembic migration for tenants table
- [ ] Insert default tenant for existing data

**Acceptance:** Tenants table exists with default row

---

**Task 1.2.2: Add tenant_id to Existing Tables**
- [ ] Create migration to add `tenant_id` to:
  - Product
  - ChannelListing
  - Order
  - OrderLine
  - Location
  - StockItem
  - StockMovement
  - Vendor (and related)
  - PurchaseOrder (and related)
  - Category
- [ ] Set all existing rows to default tenant
- [ ] Add NOT NULL constraint after update
- [ ] Add foreign key constraint
- [ ] Add index on tenant_id

**Acceptance:** All tables have tenant_id, existing data assigned

---

**Task 1.2.3: Enable Row-Level Security**
- [ ] Create migration to enable RLS on all tables
- [ ] Create tenant isolation policy:
  ```sql
  CREATE POLICY tenant_isolation ON "Product"
      USING (tenant_id = current_setting('app.current_tenant', true)::uuid);
  ```
- [ ] Create bypass role for migrations/admin
- [ ] Test RLS works (query returns only tenant's data)

**Acceptance:** Queries only return current tenant's data

---

**Task 1.2.4: Tenant Context Middleware**
- [ ] Create FastAPI middleware/dependency to:
  - Extract tenant_id from JWT claims
  - Set `app.current_tenant` on database session
  - Handle missing/invalid tenant
- [ ] Add to all routes via dependency

**Acceptance:** Routes automatically filter by tenant

---

### 1.3 Auth System

**Task 1.3.1: User Model**
- [ ] Create `User` SQLAlchemy model (fastapi-users compatible):
  ```python
  class User(SQLAlchemyBaseUserTableUUID, Base):
      tenant_id: UUID (FK)
      role: str  # 'admin' | 'member'
      first_name: str
      last_name: str
      created_at: datetime
      updated_at: datetime
  ```
- [ ] Create Alembic migration

**Acceptance:** Users table exists with tenant association

---

**Task 1.3.2: fastapi-users Setup**
- [ ] Configure UserManager
- [ ] Configure JWTStrategy with tenant_id in claims
- [ ] Configure authentication backend
- [ ] Create auth router endpoints:
  - POST /auth/register
  - POST /auth/login
  - POST /auth/logout
  - POST /auth/forgot-password
  - POST /auth/reset-password
  - GET /auth/me

**Acceptance:** Can register, login, get current user

---

**Task 1.3.3: Role-Based Access Control**
- [ ] Create role enum: admin, member
- [ ] Create `require_role` dependency:
  ```python
  def require_role(roles: list[str]):
      async def dependency(user: User = Depends(current_user)):
          if user.role not in roles:
              raise HTTPException(403)
          return user
      return dependency
  ```
- [ ] Apply to routes that need admin access

**Acceptance:** Admin-only routes reject members

---

**Task 1.3.4: Tenant Registration Flow**
- [ ] Create POST /tenants/register endpoint:
  - Creates new tenant
  - Creates admin user for tenant
  - Returns JWT token
- [ ] Validate unique tenant slug
- [ ] Send welcome email (optional V1)

**Acceptance:** New tenant + admin user created in one call

---

**Task 1.3.5: TypeScript Service Auth Integration**
- [ ] Add JWT validation middleware to inventory-service
- [ ] Validate token signature (shared secret or JWKS)
- [ ] Extract tenant_id and set on Prisma context
- [ ] Test: TS service rejects invalid tokens

**Acceptance:** Both services validate same JWT tokens

---

## Phase 2: Velocity Core (Week 3-4)

### 2.1 Velocity Models

**Task 2.1.1: ListingVelocity Model**
- [ ] Create SQLAlchemy model:
  ```python
  class ListingVelocity(Base):
      id: UUID
      tenant_id: UUID
      listing_id: UUID  # FK to ChannelListing
      calculated_at: datetime
      velocity_1d: Decimal
      velocity_7d: Decimal
      velocity_30d: Decimal
      trend_7d_30d: Decimal (nullable)
      was_suppressed: bool = False
  ```
- [ ] Add unique constraint: (listing_id, calculated_at)
- [ ] Create migration

**Acceptance:** Table exists, can insert velocity records

---

**Task 2.1.2: SkuConsumptionRate Model**
- [ ] Create SQLAlchemy model:
  ```python
  class SkuConsumptionRate(Base):
      id: UUID
      tenant_id: UUID
      product_id: UUID  # FK to Product
      location_id: UUID (nullable)
      calculated_at: datetime
      consumption_1d: Decimal
      consumption_7d: Decimal
      consumption_30d: Decimal
      days_of_stock: Decimal (nullable)
      reorder_urgency: str (nullable)
  ```
- [ ] Create migration

**Acceptance:** Table exists

---

**Task 2.1.3: VelocityFactor Model**
- [ ] Create SQLAlchemy model:
  ```python
  class VelocityFactor(Base):
      id: UUID
      tenant_id: UUID
      scope_type: str  # 'listing' | 'channel' | 'tenant'
      listing_id: UUID (nullable)
      channel: str (nullable)
      factor_type: str  # 'suppression' | 'promotion' | etc.
      direction: str  # 'increase' | 'decrease' | 'mixed'
      name: str
      description: str (nullable)
      effective_from: datetime
      effective_to: datetime (nullable)
      metadata: dict = {}
  ```
- [ ] Create migration

**Acceptance:** Can create factors at all scope levels

---

**Task 2.1.4: ListingStatusHistory Model**
- [ ] Create SQLAlchemy model:
  ```python
  class ListingStatusHistory(Base):
      id: UUID
      tenant_id: UUID
      listing_id: UUID
      status: str  # matches ListingStatus enum
      reason: str (nullable)
      effective_from: datetime
      effective_to: datetime (nullable)
      created_by: UUID (nullable)
  ```
- [ ] Create migration

**Acceptance:** Can track listing status changes over time

---

**Task 2.1.5: ListingSkuMapping Model (Versioned Bundles)**
- [ ] Create SQLAlchemy model:
  ```python
  class ListingSkuMapping(Base):
      id: UUID
      tenant_id: UUID
      listing_id: UUID
      product_id: UUID  # Component SKU
      quantity_per_unit: int = 1
      version: int = 1
      effective_from: datetime
      effective_to: datetime (nullable)
  ```
- [ ] Create migration

**Acceptance:** Can define bundle composition with version history

---

**Task 2.1.6: Extend OrderLine for Velocity**
- [ ] Create migration to add columns to OrderLine:
  - unit_price_currency: str = "USD"
  - unit_price_base: Decimal
  - fx_rate: Decimal (nullable)
  - cancelled_at: datetime (nullable)
  - cancelled_qty: int = 0
- [ ] Backfill unit_price_base = unit_price for existing

**Acceptance:** OrderLine has currency and cancellation fields

---

### 2.2 Velocity Calculation

**Task 2.2.1: Celery Setup**
- [ ] Create `workers/celery_app.py`:
  ```python
  from celery import Celery
  celery = Celery('copio')
  celery.config_from_object('src.config:settings')
  ```
- [ ] Configure Redis as broker
- [ ] Add Celery to docker-compose
- [ ] Create worker startup script

**Acceptance:** `celery -A src.workers.celery_app worker` starts

---

**Task 2.2.2: Velocity Calculation Service**
- [ ] Create `services/velocity.py`:
  ```python
  async def calculate_listing_velocity(
      tenant_id: UUID,
      listing_id: UUID,
      as_of: datetime
  ) -> ListingVelocity:
      # Query OrderLine for listing
      # Calculate V1, V7, V30
      # Check for suppression during period
      # Return velocity record
  ```
- [ ] Handle zero sales gracefully
- [ ] Handle new listings (< 30 days history)

**Acceptance:** Correct velocity calculated for test listing

---

**Task 2.2.3: Bulk Velocity Calculation**
- [ ] Create `services/velocity.py`:
  ```python
  async def calculate_all_velocities(tenant_id: UUID):
      # Get all active listings for tenant
      # Calculate velocity for each
      # Bulk insert results
  ```
- [ ] Optimize with single aggregation query where possible
- [ ] Log progress for long-running tenants

**Acceptance:** All listings processed in < 1 minute (typical tenant)

---

**Task 2.2.4: SKU Consumption Calculation**
- [ ] Create function to aggregate listing velocity → SKU consumption:
  ```python
  async def calculate_sku_consumption(tenant_id: UUID):
      # For each SKU:
      #   Find all listings containing this SKU
      #   Sum: listing_velocity × quantity_per_unit
      #   Calculate days_of_stock
      #   Set reorder_urgency
  ```
- [ ] Handle versioned bundles (use effective_at)

**Acceptance:** Correct consumption for bundle products

---

**Task 2.2.5: Hourly Velocity Celery Task**
- [ ] Create `workers/tasks.py`:
  ```python
  @celery.task
  def calculate_velocities_task():
      # Get all active tenants
      # For each tenant:
      #   calculate_all_velocities(tenant_id)
      #   calculate_sku_consumption(tenant_id)
  ```
- [ ] Add Celery beat schedule (hourly)
- [ ] Add error handling and retry logic
- [ ] Add monitoring/logging

**Acceptance:** Task runs hourly, all tenants processed

---

### 2.3 Velocity API

**Task 2.3.1: Velocity Endpoints**
- [ ] Create `api/v1/velocity.py`:
  - GET /velocity/listings - List all with velocity
  - GET /velocity/listings/{id} - Single listing detail
  - GET /velocity/skus - SKU consumption list
  - GET /velocity/skus/{id} - Single SKU detail
  - GET /velocity/dashboard - Summary stats
- [ ] Add filtering: channel, date range, health status
- [ ] Add pagination
- [ ] Add sorting

**Acceptance:** Can retrieve velocity data via API

---

**Task 2.3.2: Velocity Schemas**
- [ ] Create Pydantic schemas:
  ```python
  class ListingVelocityResponse(BaseModel):
      listing_id: UUID
      title: str
      channel: str
      velocity_1d: Decimal
      velocity_7d: Decimal
      velocity_30d: Decimal
      trend: Decimal
      health_status: str  # 'healthy' | 'declining' | 'dead_stock'
  ```
- [ ] Create dashboard summary schema

**Acceptance:** Type-safe API responses

---

**Task 2.3.3: Factor CRUD Endpoints**
- [ ] Create `api/v1/factors.py`:
  - POST /velocity/factors - Create factor
  - GET /velocity/factors - List factors
  - GET /velocity/factors/{id} - Get factor
  - PUT /velocity/factors/{id} - Update factor
  - DELETE /velocity/factors/{id} - Delete factor
- [ ] Validate scope_type with listing_id/channel
- [ ] Validate date ranges

**Acceptance:** Full CRUD for velocity factors

---

**Task 2.3.4: Listing Suppression Endpoints**
- [ ] Create endpoints:
  - POST /listings/{id}/suppress - Mark suppressed
  - POST /listings/{id}/activate - Reactivate
  - GET /listings/{id}/status-history - Get history
- [ ] Auto-create VelocityFactor when suppressing
- [ ] Record in ListingStatusHistory

**Acceptance:** Can suppress/activate with full audit trail

---

## Phase 3: Channel Sync (Week 5-6)

### 3.1 Amazon SP-API

**Task 3.1.1: Amazon OAuth Flow**
- [ ] Create `services/amazon.py` with SP-API client
- [ ] Implement OAuth authorization URL generation
- [ ] Implement callback handler (exchange code for tokens)
- [ ] Store refresh token securely (encrypted)
- [ ] Implement token refresh logic

**Acceptance:** Can authorize Amazon seller account

---

**Task 3.1.2: Amazon Orders Sync**
- [ ] Implement getOrders API call
- [ ] Map Amazon order → Copio Order model
- [ ] Handle pagination
- [ ] Implement incremental sync (since last sync)
- [ ] Create Celery task for periodic sync

**Acceptance:** Orders sync from Amazon to Copio

---

**Task 3.1.3: Amazon Listings Sync**
- [ ] Implement getCatalogItem API call
- [ ] Implement getListingsItem API call
- [ ] Map to ChannelListing model
- [ ] Detect new listings
- [ ] Create sync task

**Acceptance:** Listings sync from Amazon

---

**Task 3.1.4: Amazon Inventory Sync**
- [ ] Implement getInventorySummaries API call
- [ ] Update StockItem for FBA locations
- [ ] Handle multiple fulfillment centers

**Acceptance:** FBA inventory quantities synced

---

### 3.2 Shopify

**Task 3.2.1: Shopify OAuth Flow**
- [ ] Create `services/shopify.py`
- [ ] Implement OAuth install URL
- [ ] Implement callback (exchange for access token)
- [ ] Store access token securely
- [ ] Handle token refresh (if applicable)

**Acceptance:** Can install Shopify app

---

**Task 3.2.2: Shopify Orders Webhook**
- [ ] Register order webhook (orders/create, orders/updated)
- [ ] Create webhook endpoint in API
- [ ] Validate webhook signature
- [ ] Map Shopify order → Copio Order
- [ ] Process webhook asynchronously (Celery)

**Acceptance:** Orders flow in real-time via webhook

---

**Task 3.2.3: Shopify Products Sync**
- [ ] Implement products list API call
- [ ] Map to ChannelListing + Product
- [ ] Handle variants
- [ ] Create sync task

**Acceptance:** Shopify products synced

---

**Task 3.2.4: Shopify Inventory Sync**
- [ ] Implement inventory levels API
- [ ] Map to StockItem
- [ ] Handle multiple locations

**Acceptance:** Shopify inventory synced

---

### 3.3 Sync Infrastructure

**Task 3.3.1: Sync Log Model**
- [ ] Create SyncLog model:
  ```python
  class SyncLog(Base):
      id: UUID
      tenant_id: UUID
      channel: str
      sync_type: str  # 'orders' | 'listings' | 'inventory'
      status: str  # 'running' | 'success' | 'failed'
      started_at: datetime
      completed_at: datetime (nullable)
      records_processed: int
      error_message: str (nullable)
  ```
- [ ] Create migration

**Acceptance:** Sync history tracked

---

**Task 3.3.2: Channel Credentials Model**
- [ ] Create ChannelCredential model:
  ```python
  class ChannelCredential(Base):
      id: UUID
      tenant_id: UUID
      channel: str
      credentials: dict  # encrypted
      status: str
      last_used_at: datetime
      expires_at: datetime (nullable)
  ```
- [ ] Implement encryption for credentials
- [ ] Create migration

**Acceptance:** Secure credential storage

---

**Task 3.3.3: Sync Status API**
- [ ] Create endpoints:
  - GET /sync/status - Overall sync status
  - GET /sync/logs - Sync history
  - POST /sync/trigger/{channel} - Manual sync trigger
- [ ] Show last sync time per channel
- [ ] Show error states

**Acceptance:** Users can monitor sync health

---

## Phase 4: Integration (Week 7-8)

### 4.1 API Gateway

**Task 4.1.1: Unified Entry Point**
- [ ] Configure nginx/traefik/caddy:
  - /api/v1/auth/* → Python
  - /api/v1/velocity/* → Python
  - /api/v1/sync/* → Python
  - /api/v1/* → TypeScript (fallback)
- [ ] Add to docker-compose
- [ ] Handle CORS

**Acceptance:** Single API URL, correct routing

---

**Task 4.1.2: Health Checks**
- [ ] Add /health endpoint to Python service
- [ ] Add /health endpoint to TypeScript service
- [ ] Configure load balancer health checks

**Acceptance:** Services monitored for availability

---

### 4.2 Frontend Dashboard

**Task 4.2.1: Velocity Dashboard Page**
- [ ] Create `/dashboard/velocity` page
- [ ] Show summary cards:
  - Total listings
  - Healthy / Declining / Dead stock counts
  - Top movers (highest velocity)
  - Problem listings (biggest declines)
- [ ] Add date range selector

**Acceptance:** Overview of velocity health

---

**Task 4.2.2: Listing Velocity Table**
- [ ] Create data table with columns:
  - Listing title
  - Channel
  - V1 / V7 / V30
  - Trend indicator
  - Status
- [ ] Add filtering by channel, health status
- [ ] Add sorting
- [ ] Link to listing detail

**Acceptance:** Can browse all listings with velocity

---

**Task 4.2.3: Listing Detail with Velocity**
- [ ] Add velocity section to listing detail page:
  - Current velocity metrics
  - Trend chart (30-day history)
  - Active factors affecting this listing
  - Status history
- [ ] Add suppress/activate buttons (admin only)

**Acceptance:** Full velocity context on listing page

---

**Task 4.2.4: Factor Management UI**
- [ ] Create factor list view
- [ ] Create factor create/edit dialog:
  - Factor type selector
  - Scope selector (listing/channel/tenant)
  - Date range picker
  - Description
- [ ] Show active factors on dashboard

**Acceptance:** Users can manage velocity factors

---

**Task 4.2.5: SKU Consumption View**
- [ ] Create `/dashboard/inventory/consumption` page
- [ ] Show SKU list with:
  - Consumption rate (30d)
  - Days of stock
  - Reorder urgency (color coded)
- [ ] Filter by urgency
- [ ] Link to reorder action (V2)

**Acceptance:** Ops team can see reorder needs

---

## Testing & Documentation

**Task T.1: Unit Tests**
- [ ] Velocity calculation tests
- [ ] Factor overlap tests
- [ ] Bundle consumption tests
- [ ] Auth/RBAC tests

**Task T.2: Integration Tests**
- [ ] API endpoint tests
- [ ] Channel sync mock tests
- [ ] Multi-tenant isolation tests

**Task T.3: Documentation**
- [ ] API documentation (auto-generated OpenAPI)
- [ ] Developer setup guide
- [ ] Channel integration guides (Amazon, Shopify)

---

## Milestone Checklist

### End of Week 2
- [ ] Python service running
- [ ] Multi-tenancy migrated
- [ ] Auth working (register, login)
- [ ] Both services share JWT tokens

### End of Week 4
- [ ] Velocity tables exist
- [ ] Hourly calculation job running
- [ ] Velocity API endpoints working
- [ ] Factor CRUD working

### End of Week 6
- [ ] Amazon OAuth + order sync working
- [ ] Shopify OAuth + order sync working
- [ ] Listings syncing from both channels

### End of Week 8
- [ ] API gateway routing both services
- [ ] Velocity dashboard in frontend
- [ ] Factor management UI
- [ ] Ready for user testing

---

*Last updated: 2025-01-27*
