# User Management Module — Design Document

> **Status:** Approved
> **Date:** 2026-01-31
> **Author:** J + Jarvis

## Overview

Granular permission system for Copio ERP with dynamic roles, invite-only user management, and comprehensive audit logging.

## Architecture Decisions

### Permission Model: Hybrid RBAC + Fine-Grained Permissions

- **Casbin** for policy enforcement (production-ready, async, multi-tenant)
- Permissions structured as `resource:action` (e.g., `products:create`, `purchase_orders:receive`)
- Roles are collections of permissions, fully customizable per tenant
- System roles (Admin, Viewer) are templates — tenant admins create custom roles

### Two-Tier Admin Structure

1. **Super Admin** (J) — god-mode across all tenants, can impersonate
2. **Tenant Admin** — manages users and roles within their tenant only

### User Onboarding: Invite-Only

- Admin sends invite with email + role
- User receives magic link, sets password
- No self-registration (ERP security requirement)

### Security Principles

| Principle | Implementation |
|-----------|----------------|
| Least Privilege | Users get only permissions their role grants |
| Deny Override | Explicit denies beat allows (Casbin priority) |
| Audit Everything | Log all auth events, permission checks, sensitive actions |
| Separate Auth/Authz | fastapi-users for auth, Casbin for authorization |

---

## Permission Matrix

### Resources & Actions

| Resource | View | Create | Edit | Delete | Special Actions |
|----------|------|--------|------|--------|-----------------|
| products | ✓ | ✓ | ✓ | ✓ | — |
| inventory | ✓ | — | — | — | adjust, transfer |
| vendors | ✓ | ✓ | ✓ | ✓ | — |
| purchase_orders | ✓ | ✓ | ✓ | ✓ | receive, approve |
| locations | ✓ | ✓ | ✓ | ✓ | — |
| categories | ✓ | ✓ | ✓ | ✓ | — |
| channels | ✓ | ✓ | ✓ | ✓ | sync |
| users | ✓ | — | ✓ | ✓ | invite |
| roles | ✓ | ✓ | ✓ | ✓ | — |
| settings | ✓ | — | ✓ | — | — |
| audit_log | ✓ | — | — | — | export |

### System Roles (Templates)

| Role | Permissions |
|------|-------------|
| Admin | `*:*` (all) |
| Manager | All except `users:delete`, `roles:*`, `settings:edit` |
| Warehouse | `inventory:*`, `purchase_orders:view,receive`, `products:view`, `locations:view` |
| Viewer | `*:view` only |

---

## Database Schema

### New Tables

```sql
-- Permission policies (Casbin adapter)
CREATE TABLE casbin_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ptype VARCHAR(10) NOT NULL,  -- 'p' for policy, 'g' for grouping
    v0 VARCHAR(255),  -- subject (user_id or role)
    v1 VARCHAR(255),  -- object (resource:action or role)
    v2 VARCHAR(255),  -- action (for policies)
    v3 VARCHAR(255),  -- domain (tenant_id)
    v4 VARCHAR(255),
    v5 VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Roles per tenant
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    is_system BOOLEAN DEFAULT FALSE,  -- system roles can't be deleted
    permissions JSONB NOT NULL DEFAULT '[]',  -- ["products:view", "products:create"]
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- User role assignments
CREATE TABLE user_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, role_id)
);

-- User invites
CREATE TABLE user_invites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    email VARCHAR(255) NOT NULL,
    role_id UUID NOT NULL REFERENCES roles(id),
    token VARCHAR(255) UNIQUE NOT NULL,
    invited_by UUID NOT NULL REFERENCES users(id),
    expires_at TIMESTAMPTZ NOT NULL,
    accepted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Audit log
CREATE TABLE audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    user_id UUID REFERENCES users(id),  -- null for system events
    action VARCHAR(50) NOT NULL,  -- login, logout, permission_denied, role_changed, etc.
    resource_type VARCHAR(50),
    resource_id UUID,
    details JSONB,  -- additional context
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_audit_log_tenant_created ON audit_log(tenant_id, created_at DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_id, created_at DESC);
```

### User Model Updates

```python
# Add to existing User model
is_super_admin: Mapped[bool] = mapped_column(default=False)

# Remove old 'role' field, use user_roles table instead
```

---

## UI Pages

### Settings Section (All Tenant Admins)

| Route | Purpose |
|-------|---------|
| `/settings/users` | List users, invite, edit role, deactivate |
| `/settings/roles` | List roles, create custom roles |
| `/settings/roles/[id]` | Edit role with permission matrix |
| `/settings/audit-log` | View audit trail, filter, export |

### Super Admin Section

| Route | Purpose |
|-------|---------|
| `/admin/tenants` | List all tenants, impersonate |
| `/admin/system` | Global settings |

---

## API Endpoints

### Users

- `GET /api/v1/users` — list users in tenant
- `POST /api/v1/users/invite` — send invite email
- `GET /api/v1/users/invite/:token` — validate invite token
- `POST /api/v1/users/invite/:token/accept` — accept invite, set password
- `PATCH /api/v1/users/:id` — update user (role, active status)
- `DELETE /api/v1/users/:id` — deactivate user

### Roles

- `GET /api/v1/roles` — list roles in tenant
- `POST /api/v1/roles` — create custom role
- `GET /api/v1/roles/:id` — get role with permissions
- `PATCH /api/v1/roles/:id` — update role permissions
- `DELETE /api/v1/roles/:id` — delete custom role

### Permissions

- `GET /api/v1/permissions` — list all available permissions (for UI)
- `GET /api/v1/me/permissions` — current user's effective permissions

### Audit Log

- `GET /api/v1/audit-log` — paginated audit log with filters
- `GET /api/v1/audit-log/export` — CSV export

---

## Implementation Notes

### Casbin Model (RBAC with domains)

```ini
[request_definition]
r = sub, dom, obj, act

[policy_definition]
p = sub, dom, obj, act

[role_definition]
g = _, _, _

[policy_effect]
e = some(where (p.eft == allow))

[matchers]
m = g(r.sub, p.sub, r.dom) && r.dom == p.dom && r.obj == p.obj && r.act == p.act
```

### Permission Check Flow

1. Request comes in with user JWT
2. Extract `user_id` and `tenant_id` from token
3. Call `enforcer.enforce(user_id, tenant_id, resource, action)`
4. Casbin checks user's roles and their permissions
5. Log result to audit_log (success or denial)
6. Return 403 if denied

### Audit Logging Middleware

```python
@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    # Log sensitive actions based on route + method
    if should_audit(request.url.path, request.method):
        await log_audit_event(request, response)
    return response
```

---

## Out of Scope (Future)

- OAuth/SSO integration
- API key management
- Two-factor authentication
- Resource-level permissions (e.g., "only vendor X's POs")
- Permission inheritance/hierarchy
