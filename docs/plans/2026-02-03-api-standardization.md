# API Response Standardization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Standardize all API list endpoints to use consistent pagination pattern matching industry best practices (Stripe, GitHub).

**Architecture:** All list endpoints return `{ data: [...], pagination: { page, pageSize, total, totalPages } }`. Single items return the object directly (no wrapper). Frontend uses a shared API client that handles this consistently.

**Tech Stack:** FastAPI + Pydantic (backend), React + TypeScript (frontend)

---

## Current State

| Pattern | Endpoints |
|---------|-----------|
| `PaginatedResponse` (correct) | products, channel_listings, stock_movements |
| `{ data, total }` (partial) | roles |
| `list[...]` (raw array) | locations, categories, vendors, stock_items, users, vendor_*, purchase_orders |
| `dict` (untyped) | purchase_orders list |

## Target State

All list endpoints use:
```python
PaginatedResponse[ItemType]  # { data: [...], pagination: {...} }
```

---

### Task 1: Update Common Schema

**Files:**
- Modify: `packages/api/src/schemas/common.py`

**Step 1: Update PaginatedResponse to use camelCase for frontend**

```python
"""Common schema components."""

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class Pagination(BaseModel):
    """Pagination info."""

    page: int
    page_size: int
    total: int
    total_pages: int

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
        alias_generator=lambda s: ''.join(
            word.capitalize() if i else word
            for i, word in enumerate(s.split('_'))
        ),
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    data: list[T]
    pagination: Pagination
```

**Step 2: Commit**

```bash
git add packages/api/src/schemas/common.py
git commit -m "chore: update PaginatedResponse schema with camelCase aliases"
```

---

### Task 2: Standardize Locations API

**Files:**
- Modify: `packages/api/src/api/v1/locations.py`

**Step 1: Update list endpoint to use pagination**

```python
from sqlalchemy import func

from src.schemas.common import PaginatedResponse, Pagination

@router.get("/", response_model=PaginatedResponse[LocationRead])
async def list_locations(
    session: DbSession,
    current_user: CurrentUser,
    type: LocationType | None = None,
    active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all locations for the tenant."""
    query = select(Location).where(Location.tenant_id == current_user.tenant_id)

    if type:
        query = query.where(Location.type == type)
    if active is not None:
        query = query.where(Location.is_active == active)

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Location.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    locations = result.scalars().all()

    return PaginatedResponse(
        data=[LocationRead.model_validate(loc) for loc in locations],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/locations.py
git commit -m "feat(api): standardize locations list endpoint with pagination"
```

---

### Task 3: Standardize Roles API

**Files:**
- Modify: `packages/api/src/api/v1/roles.py`

**Step 1: Replace RoleListResponse with PaginatedResponse**

Remove the custom `RoleListResponse` class and update the endpoint:

```python
from src.schemas.common import PaginatedResponse, Pagination

# Remove RoleListResponse class

@router.get("", response_model=PaginatedResponse[RoleResponse])
async def list_roles(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("roles:view")),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all roles for the tenant."""
    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(Role).where(Role.tenant_id == user.tenant_id)
    )
    total = count_result.scalar_one()

    # Fetch roles
    offset = (page - 1) * page_size
    result = await session.execute(
        select(Role)
        .where(Role.tenant_id == user.tenant_id)
        .order_by(Role.name)
        .offset(offset)
        .limit(page_size)
    )
    roles = result.scalars().all()

    return PaginatedResponse(
        data=[RoleResponse.model_validate(r) for r in roles],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/roles.py
git commit -m "feat(api): standardize roles list endpoint with pagination"
```

---

### Task 4: Standardize Vendors API

**Files:**
- Modify: `packages/api/src/api/v1/vendors.py`

**Step 1: Update list endpoint**

```python
from src.schemas.common import PaginatedResponse, Pagination

@router.get("/", response_model=PaginatedResponse[VendorListItem])
async def list_vendors(
    session: DbSession,
    current_user: CurrentUser,
    tier: VendorTier | None = None,
    status: VendorStatus | None = Query(None),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
    _perm=Depends(require_permission("vendors:view")),
):
    """List vendors with filtering."""
    query = select(Vendor).where(Vendor.tenant_id == current_user.tenant_id)

    if tier:
        query = query.where(Vendor.tier == tier)
    if status:
        query = query.where(Vendor.status == status)
    if search:
        search_filter = or_(
            Vendor.name.ilike(f"%{search}%"),
            Vendor.code.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = (
        query
        .options(selectinload(Vendor.contacts), selectinload(Vendor.addresses))
        .order_by(Vendor.name)
        .offset(offset)
        .limit(page_size)
    )
    result = await session.execute(query)
    vendors = result.scalars().all()

    return PaginatedResponse(
        data=[VendorListItem.model_validate(v) for v in vendors],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/vendors.py
git commit -m "feat(api): standardize vendors list endpoint with pagination"
```

---

### Task 5: Standardize Categories API

**Files:**
- Modify: `packages/api/src/api/v1/categories.py`

**Step 1: Update list endpoint (keep tree endpoint as-is for hierarchy)**

```python
from src.schemas.common import PaginatedResponse, Pagination

@router.get("/", response_model=PaginatedResponse[CategoryRead])
async def list_categories(
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize"),
):
    """List all categories (flat)."""
    query = select(Category).where(Category.tenant_id == current_user.tenant_id)

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Category.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    categories = result.scalars().all()

    return PaginatedResponse(
        data=[CategoryRead.model_validate(c) for c in categories],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/categories.py
git commit -m "feat(api): standardize categories list endpoint with pagination"
```

---

### Task 6: Standardize Stock Items API

**Files:**
- Modify: `packages/api/src/api/v1/stock_items.py`

**Step 1: Update all list endpoints**

Update the main list, by-location, and by-product endpoints to use PaginatedResponse.

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/stock_items.py
git commit -m "feat(api): standardize stock_items list endpoints with pagination"
```

---

### Task 7: Standardize Users API

**Files:**
- Modify: `packages/api/src/api/v1/users.py`

**Step 1: Update list endpoint**

```python
from src.schemas.common import PaginatedResponse, Pagination

@router.get("", response_model=PaginatedResponse[UserResponse])
async def list_users(
    session: DbSession,
    user: User = Depends(get_current_user_with_dev_bypass),
    _perm=Depends(require_permission("users:view")),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all users in the tenant."""
    query = select(User).where(User.tenant_id == user.tenant_id)

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    result = await session.execute(
        query.order_by(User.email).offset(offset).limit(page_size)
    )
    users = result.scalars().all()

    return PaginatedResponse(
        data=[UserResponse.model_validate(u) for u in users],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/users.py
git commit -m "feat(api): standardize users list endpoint with pagination"
```

---

### Task 8: Standardize Purchase Orders API

**Files:**
- Modify: `packages/api/src/api/v1/purchase_orders.py`

**Step 1: Fix the main list endpoint (currently returns untyped dict)**

Replace `response_model=dict` with proper `PaginatedResponse[PurchaseOrderListItem]`.

**Step 2: Update follow-ups and in-transit endpoints**

**Step 3: Commit**

```bash
git add packages/api/src/api/v1/purchase_orders.py
git commit -m "feat(api): standardize purchase_orders list endpoints with pagination"
```

---

### Task 9: Standardize Vendor Sub-resources APIs

**Files:**
- Modify: `packages/api/src/api/v1/vendor_products.py`
- Modify: `packages/api/src/api/v1/vendor_addresses.py`
- Modify: `packages/api/src/api/v1/vendor_contacts.py`
- Modify: `packages/api/src/api/v1/vendor_documents.py`

**Step 1: Update all by-vendor list endpoints to use PaginatedResponse**

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/vendor_*.py
git commit -m "feat(api): standardize vendor sub-resource list endpoints with pagination"
```

---

### Task 10: Standardize Audit Log API

**Files:**
- Modify: `packages/api/src/api/v1/audit_log.py`

**Step 1: Replace AuditLogResponse with PaginatedResponse**

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/audit_log.py
git commit -m "feat(api): standardize audit_log list endpoint with pagination"
```

---

### Task 11: Create Frontend API Client

**Files:**
- Create: `packages/web/src/lib/api-client.ts`

**Step 1: Create typed API client**

```typescript
import { useAuth } from "./auth";

export interface Pagination {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export interface ApiError {
  detail: string;
  status: number;
}

class ApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const headers: HeadersInit = {
      "Content-Type": "application/json",
      ...options.headers,
    };

    if (this.token) {
      (headers as Record<string, string>)["Authorization"] = `Bearer ${this.token}`;
    }

    const res = await fetch(`/api/v1${endpoint}`, {
      ...options,
      headers,
    });

    if (!res.ok) {
      const error = await res.json().catch(() => ({ detail: "Request failed" }));
      throw { detail: error.detail || "Request failed", status: res.status } as ApiError;
    }

    if (res.status === 204) {
      return undefined as T;
    }

    return res.json();
  }

  // Generic list with pagination
  async list<T>(
    endpoint: string,
    params?: Record<string, string | number | boolean | undefined>
  ): Promise<PaginatedResponse<T>> {
    const searchParams = new URLSearchParams();
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined) {
          searchParams.set(key, String(value));
        }
      });
    }
    const query = searchParams.toString();
    return this.request<PaginatedResponse<T>>(
      `${endpoint}${query ? `?${query}` : ""}`
    );
  }

  // Single item
  async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint);
  }

  // Create
  async post<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // Update
  async patch<T>(endpoint: string, data: unknown): Promise<T> {
    return this.request<T>(endpoint, {
      method: "PATCH",
      body: JSON.stringify(data),
    });
  }

  // Delete
  async delete(endpoint: string): Promise<void> {
    return this.request<void>(endpoint, { method: "DELETE" });
  }
}

export const api = new ApiClient();

// Hook for components
export function useApiClient() {
  const { token } = useAuth();
  api.setToken(token);
  return api;
}
```

**Step 2: Commit**

```bash
git add packages/web/src/lib/api-client.ts
git commit -m "feat(web): add typed API client with pagination support"
```

---

### Task 12: Update Frontend Pages to Use New API Client

**Files:**
- Modify: `packages/web/src/app/settings/roles/page.tsx`
- Modify: `packages/web/src/app/locations/page.tsx`
- Modify: `packages/web/src/app/vendors/page.tsx`
- Modify: `packages/web/src/app/settings/users/page.tsx`

**Step 1: Update roles page**

```typescript
// Replace manual fetch with api client
const { data: rolesData } = await api.list<Role>("/roles");
setRoles(rolesData.data);
```

**Step 2: Update other pages similarly**

**Step 3: Commit**

```bash
git add packages/web/src/app
git commit -m "feat(web): update pages to use standardized API client"
```

---

## Summary

After implementation:
- All list endpoints return `{ data: [...], pagination: { page, pageSize, total, totalPages } }`
- Frontend has typed API client that handles pagination consistently
- Single item endpoints return object directly (unchanged)
- Error responses remain `{ detail: "..." }`
