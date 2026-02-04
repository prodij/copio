# God-Mode Admin Design

**Date:** 2026-02-04
**Status:** Draft
**Author:** James + Claude

## Overview

God-mode provides superusers with cross-tenant visibility and full control over the Copio platform. This design covers tenant management, user operations, data visibility, and alerting.

### Goals

1. **Full Control**: View and modify any tenant, user, or data across the platform
2. **Operational Visibility**: Dashboards showing health and activity metrics
3. **Proactive Alerting**: Configurable thresholds that trigger notifications
4. **Audit Everything**: Track all admin actions with before/after diffs
5. **Extractable Architecture**: Design for future separation to `admin.copio.com`

### Non-Goals (for now)

- Tiered admin permissions (future: support staff with limited access)
- Billing/subscription management
- Full session recording (page views, searches)

---

## Architecture

### Access Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     /admin/* routes                             │
│          (superuser-only, extracted later to subdomain)         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    /api/v1/admin/*                              │
│         All admin endpoints under single prefix                 │
│         require_superuser dependency on all routes              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AdminAuditLog                               │
│   Records: actor, action, target, before/after, timestamp       │
└─────────────────────────────────────────────────────────────────┘
```

### Key Principles

1. **Tenant-unscoped queries**: Admin endpoints bypass normal `tenant_id` filtering
2. **Explicit over implicit**: Every cross-tenant action requires specifying the target tenant
3. **Audit everything**: Middleware logs all mutating admin actions with diffs
4. **Extractable**: Clean separation so `/admin` can become `admin.copio.com` later

### New Database Models

| Model | Purpose |
|-------|---------|
| `AdminAuditLog` | Tracks all admin actions with before/after JSON |
| `ImpersonationSession` | Tracks active impersonations for safety |
| `AlertRule` | Configurable thresholds for notifications |
| `AlertEvent` | Triggered alerts history |

---

## Feature 1: Tenant Management

### Tenant List View (`/admin/tenants`)

| Column | Description |
|--------|-------------|
| Name / Slug | Tenant identity with link to detail |
| Status | Active, Suspended, Trial, Churned |
| Users | Count with link to filtered user list |
| Products | Count of products |
| Created | When tenant signed up |
| Last Activity | Most recent user login or API call |
| Health | Red/yellow/green indicator (sync errors, failed jobs) |

**Filtering & Search**
- Search by name, slug, email domain
- Filter by status, date range, health status
- Sort by any column

### Tenant Detail View (`/admin/tenants/[id]`)

```
┌─────────────────────────────────────────────────────────────────┐
│  Acme Corp (acme)                            [Suspend] [Delete] │
│  Status: Active    Created: 2024-01-15    Last active: 2 hrs ago│
├─────────────────────────────────────────────────────────────────┤
│  [Overview] [Users] [Data] [Audit Log] [Settings]               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Quick Stats                    Health Issues                   │
│  ├─ 5 users (2 active today)    ├─ 3 sync errors (last 24h)    │
│  ├─ 1,234 products              └─ 0 failed jobs               │
│  ├─ 89 orders (this month)                                     │
│  └─ 12 locations                                                │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Tenant Actions

| Action | Behavior |
|--------|----------|
| **Suspend** | Blocks all user logins, API calls return 403, data preserved |
| **Reactivate** | Restores access after suspension |
| **Delete** | Soft-delete with 30-day recovery window, then hard purge |
| **Edit Settings** | Modify tenant timezone, currency, feature flags |
| **Export Data** | Generate full data export (GDPR compliance) |

### API Endpoints

```
GET    /api/v1/admin/tenants              # List with filters
GET    /api/v1/admin/tenants/:id          # Detail with stats
PATCH  /api/v1/admin/tenants/:id          # Update settings
POST   /api/v1/admin/tenants/:id/suspend
POST   /api/v1/admin/tenants/:id/reactivate
DELETE /api/v1/admin/tenants/:id          # Soft delete
POST   /api/v1/admin/tenants/:id/export   # Trigger export job
```

---

## Feature 2: User Operations

### User List View (`/admin/users`)

| Column | Description |
|--------|-------------|
| Email | Primary identifier with link to detail |
| Name | Full name |
| Tenant | Link to tenant (key cross-tenant feature) |
| Role | Admin / Member + RBAC roles |
| Status | Active, Unverified, Locked, Suspended |
| Last Login | Timestamp |
| Created | Registration date |

**Filtering & Search**
- Global search by email, name (across all tenants)
- Filter by tenant, status, role, date range
- "Show only locked" / "Show only unverified" quick filters

### User Detail View (`/admin/users/[id]`)

```
┌─────────────────────────────────────────────────────────────────┐
│  john@acme.com                    [Impersonate] [Reset Password]│
│  John Smith • Acme Corp (acme)                                  │
│  Status: Active    Role: Admin    Last login: 3 hours ago       │
├─────────────────────────────────────────────────────────────────┤
│  [Profile] [Sessions] [Audit Log] [API Keys]                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Account Info                   Active Sessions                 │
│  ├─ Email verified: Yes         ├─ Chrome/Mac - 3 hrs ago      │
│  ├─ MFA enabled: No             └─ Mobile App - 1 day ago      │
│  ├─ Created: 2024-01-15                                        │
│  └─ API Keys: 2 active                                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### User Actions

| Action | Behavior |
|--------|----------|
| **Impersonate** | Start session as this user (see below) |
| **Force Password Reset** | Invalidates password, sends reset email |
| **Unlock Account** | Clears failed login attempts, re-enables access |
| **Revoke Sessions** | Logs user out everywhere |
| **Suspend** | Blocks login without affecting tenant |
| **Verify Email** | Manually mark email as verified |
| **Delete** | Removes user (with confirmation) |

### Impersonation Flow

```
┌──────────────────────────────────────────────────────────────────┐
│ 1. Admin clicks "Impersonate" on user detail page                │
│ 2. System creates ImpersonationSession record:                   │
│    { admin_id, target_user_id, started_at, reason (optional) }   │
│ 3. Admin's session gets impersonation token (JWT claim or cookie)│
│ 4. All requests now execute as target user                       │
│ 5. Floating banner appears:                                      │
│    ┌────────────────────────────────────────────────────────────┐│
│    │ 👁 Impersonating john@acme.com         [Exit Impersonation]││
│    └────────────────────────────────────────────────────────────┘│
│ 6. Admin clicks "Exit" → returns to admin session                │
│ 7. ImpersonationSession marked ended_at                          │
└──────────────────────────────────────────────────────────────────┘
```

### Impersonation Safety Rules

- Cannot impersonate other superusers
- All actions while impersonating logged with `impersonated_by` field
- Auto-expire after 1 hour (configurable)
- Reason field optional but encouraged for audit

### API Endpoints

```
GET    /api/v1/admin/users                    # List with filters
GET    /api/v1/admin/users/:id                # Detail with sessions
PATCH  /api/v1/admin/users/:id                # Update profile
POST   /api/v1/admin/users/:id/impersonate    # Start impersonation
DELETE /api/v1/admin/impersonation            # End impersonation
POST   /api/v1/admin/users/:id/reset-password
POST   /api/v1/admin/users/:id/unlock
POST   /api/v1/admin/users/:id/revoke-sessions
POST   /api/v1/admin/users/:id/verify-email
POST   /api/v1/admin/users/:id/suspend
DELETE /api/v1/admin/users/:id                # Delete user
```

---

## Feature 3: Data Visibility & Dashboards

### Admin Dashboard (`/admin`)

Three-panel layout showing system health at a glance:

```
┌─────────────────────────────────────────────────────────────────┐
│  God-Mode Dashboard                           Last updated: now │
├───────────────────────┬───────────────────────┬─────────────────┤
│   HEALTH STATUS       │   TODAY'S ACTIVITY    │  ALERTS (3)     │
│                       │                       │                 │
│   ● Sync Errors: 7    │   Orders: 142         │  ⚠ Acme: 5 sync │
│   ● Failed Jobs: 0    │   New Users: 3        │    errors       │
│   ● API Errors: 12    │   Active Users: 47    │  ⚠ Beta Corp:   │
│   ● Stuck Orders: 2   │   Products Added: 89  │    no activity  │
│                       │   API Calls: 12.4k    │  ● Alert rule   │
│   [View Details]      │   [View Details]      │    triggered    │
└───────────────────────┴───────────────────────┴─────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  TENANT HEALTH OVERVIEW                        [Export CSV]     │
├──────────────┬────────┬────────┬────────┬────────┬──────────────┤
│ Tenant       │ Users  │ Orders │ Sync ❌│ Health │ Last Active  │
├──────────────┼────────┼────────┼────────┼────────┼──────────────┤
│ 🔴 Acme Corp │ 5      │ 23     │ 5      │ ██░░░  │ 2 min ago    │
│ 🟡 Beta Inc  │ 12     │ 0      │ 0      │ ███░░  │ 3 days ago   │
│ 🟢 Gamma LLC │ 8      │ 45     │ 0      │ █████  │ 1 min ago    │
└──────────────┴────────┴────────┴────────┴────────┴──────────────┘
```

### Health Indicators

| Color | Meaning |
|-------|---------|
| 🟢 Green | No issues, active recently |
| 🟡 Yellow | Minor issues OR inactive 3+ days |
| 🔴 Red | Sync errors, failed jobs, or stuck orders |

### Cross-Tenant Data Views

| View | Purpose | Path |
|------|---------|------|
| **Orders** | All orders across tenants, filterable | `/admin/orders` |
| **Sync Status** | Marketplace sync jobs, errors, retry queue | `/admin/sync` |
| **Jobs** | Background job queue health | `/admin/jobs` |
| **API Logs** | Recent API errors with stack traces | `/admin/api-logs` |
| **Audit Trail** | All admin actions (your audit log) | `/admin/audit` |

### Cross-Tenant Search (`/admin/search`)

Global search across all data:

```
┌─────────────────────────────────────────────────────────────────┐
│  🔍 Search: "SKU-12345"                      [Products ▼]       │
├─────────────────────────────────────────────────────────────────┤
│  Found 3 results across 2 tenants:                              │
│                                                                 │
│  📦 SKU-12345 - Widget Pro                                      │
│     Acme Corp • Product • In stock: 142                         │
│                                                                 │
│  📦 SKU-123456 - Widget Pro Max                                 │
│     Acme Corp • Product • In stock: 0                           │
│                                                                 │
│  📋 Order #1234 contains SKU-12345                              │
│     Beta Inc • Order • Status: Shipped                          │
└─────────────────────────────────────────────────────────────────┘
```

Searchable entities: Products, Orders, Users, Vendors, SKUs, ASINs

### API Endpoints

```
GET  /api/v1/admin/dashboard/health      # Health metrics
GET  /api/v1/admin/dashboard/activity    # Activity metrics
GET  /api/v1/admin/orders                # Cross-tenant orders
GET  /api/v1/admin/sync                  # Sync job status
GET  /api/v1/admin/jobs                  # Background jobs
GET  /api/v1/admin/api-logs              # API error logs
GET  /api/v1/admin/search?q=&type=       # Global search
```

---

## Feature 4: Alerting System

### Alert Rules (`/admin/alerts/rules`)

Configurable thresholds that trigger notifications:

```
┌─────────────────────────────────────────────────────────────────┐
│  Alert Rules                                    [+ Create Rule] │
├─────────────────────────────────────────────────────────────────┤
│  ✓ Sync Error Threshold                              [Edit] [⏸] │
│    Trigger when: sync_errors > 5 in 1 hour                      │
│    Notify: email, slack                                         │
│                                                                 │
│  ✓ Tenant Inactivity                                 [Edit] [⏸] │
│    Trigger when: no_activity > 7 days                           │
│    Notify: email                                                │
│                                                                 │
│  ✓ Failed Jobs                                       [Edit] [⏸] │
│    Trigger when: failed_jobs > 0                                │
│    Notify: email, slack                                         │
│                                                                 │
│  ⏸ High API Error Rate                              [Edit] [▶]  │
│    Trigger when: api_errors > 100 in 15 min                     │
│    Notify: slack                                                │
└─────────────────────────────────────────────────────────────────┘
```

### Built-in Alert Types

| Type | Condition | Default Threshold |
|------|-----------|-------------------|
| `sync_errors` | Marketplace sync failures | > 5 per hour |
| `failed_jobs` | Background job failures | > 0 |
| `api_errors` | 5xx responses | > 100 per 15 min |
| `stuck_orders` | Orders not progressing | > 1 hour in same status |
| `tenant_inactive` | No user activity | > 7 days |
| `low_inventory` | Stock below threshold | Configurable per-tenant |
| `impersonation_started` | Admin impersonates user | Always (audit) |

### Alert Event History (`/admin/alerts`)

```
┌─────────────────────────────────────────────────────────────────┐
│  Alert History                          [Filter ▼] [Export CSV] │
├──────────┬─────────────────────────┬──────────┬─────────────────┤
│ Time     │ Alert                   │ Tenant   │ Status          │
├──────────┼─────────────────────────┼──────────┼─────────────────┤
│ 10:23 AM │ Sync Error Threshold    │ Acme     │ 🔴 Active       │
│ 09:15 AM │ Tenant Inactivity       │ Beta Inc │ 🟡 Acknowledged │
│ Yesterday│ Failed Jobs             │ Gamma    │ ✓ Resolved      │
└──────────┴─────────────────────────┴──────────┴─────────────────┘
```

### Alert Workflow

```
Triggered → Active → Acknowledged → Resolved
              │           │
              └───────────┴──→ Auto-resolved (condition clears)
```

### Notification Channels

| Channel | Implementation |
|---------|----------------|
| **Email** | Send to superuser emails (built-in) |
| **Slack** | Webhook integration (configurable) |
| **Webhook** | Generic HTTP POST for custom integrations |

### Database Models

```python
class AlertRule(Base, TimestampMixin):
    id: UUID
    name: str
    description: str | None
    alert_type: str           # sync_errors, failed_jobs, etc.
    condition: dict           # {"operator": ">", "value": 5, "window_minutes": 60}
    notify_channels: list     # ["email", "slack"]
    enabled: bool
    tenant_id: UUID | None    # NULL = all tenants, or specific tenant

class AlertEvent(Base, TimestampMixin):
    id: UUID
    rule_id: UUID
    tenant_id: UUID | None
    triggered_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    status: str               # active, acknowledged, resolved
    context: dict             # Details about what triggered it
    acknowledged_by: UUID | None  # Admin who acknowledged
```

### API Endpoints

```
GET    /api/v1/admin/alerts/rules         # List rules
POST   /api/v1/admin/alerts/rules         # Create rule
PATCH  /api/v1/admin/alerts/rules/:id     # Update rule
DELETE /api/v1/admin/alerts/rules/:id     # Delete rule

GET    /api/v1/admin/alerts               # Alert event history
POST   /api/v1/admin/alerts/:id/acknowledge
POST   /api/v1/admin/alerts/:id/resolve
```

---

## Feature 5: Audit Logging

### Admin Audit Log (`/admin/audit`)

Dedicated log for all God-mode actions (separate from tenant audit logs):

```
┌─────────────────────────────────────────────────────────────────┐
│  Admin Audit Log                        [Filter ▼] [Export CSV] │
├──────────┬──────────────┬───────────────────────┬───────────────┤
│ Time     │ Admin        │ Action                │ Target        │
├──────────┼──────────────┼───────────────────────┼───────────────┤
│ 10:45 AM │ james@...    │ impersonation.start   │ john@acme.com │
│ 10:32 AM │ james@...    │ tenant.suspend        │ Beta Inc      │
│ 10:15 AM │ james@...    │ user.reset_password   │ bob@gamma.com │
│ 09:50 AM │ james@...    │ setting.update        │ email_verif.. │
└──────────┴──────────────┴───────────────────────┴───────────────┘
```

### Audit Detail View

Clicking a row shows the full diff:

```
┌─────────────────────────────────────────────────────────────────┐
│  Audit Event Detail                                             │
├─────────────────────────────────────────────────────────────────┤
│  Action:     tenant.update                                      │
│  Admin:      james@copio.com                                    │
│  Target:     Acme Corp (tenant)                                 │
│  Timestamp:  2026-02-04 10:32:15 UTC                           │
│  IP Address: 192.168.1.100                                      │
├─────────────────────────────────────────────────────────────────┤
│  Changes:                                                       │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  timezone:                                                  ││
│  │    - "America/Los_Angeles"                                  ││
│  │    + "America/New_York"                                     ││
│  │                                                             ││
│  │  settings.feature_flags.beta_sync:                          ││
│  │    - false                                                  ││
│  │    + true                                                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Database Model

```python
class AdminAuditLog(Base):
    id: UUID
    admin_id: UUID              # Superuser who performed action
    action: str                 # e.g., "tenant.suspend", "user.impersonate"
    target_type: str            # "tenant", "user", "setting", etc.
    target_id: UUID | None      # ID of affected entity
    target_label: str           # Human-readable: "Acme Corp", "john@acme.com"

    before_state: dict | None   # JSON snapshot before change
    after_state: dict | None    # JSON snapshot after change

    ip_address: str
    user_agent: str

    # If action was during impersonation
    impersonating_user_id: UUID | None

    created_at: datetime
```

### Tracked Actions

| Category | Actions |
|----------|---------|
| **Tenant** | create, update, suspend, reactivate, delete, export |
| **User** | update, suspend, delete, reset_password, unlock, verify_email, revoke_sessions |
| **Impersonation** | start, end |
| **Settings** | update (system settings) |
| **Alerts** | rule.create, rule.update, rule.delete, acknowledge, resolve |

### Filtering Options

- By admin (who did it)
- By action type
- By target type (tenant, user, setting)
- By target (specific tenant or user)
- By date range
- "Show only destructive" (suspend, delete, etc.)

### API Endpoints

```
GET  /api/v1/admin/audit                  # List with filters
GET  /api/v1/admin/audit/:id              # Single event detail
GET  /api/v1/admin/audit/export           # CSV/JSON export
```

### Implementation Notes

1. **Middleware approach**: Decorator on admin endpoints captures before/after automatically
2. **Async logging**: Write audit log asynchronously to not slow down requests
3. **Retention**: Keep forever (or configurable retention policy)
4. **Immutable**: Audit logs cannot be edited or deleted via API

---

## Navigation Structure

### Frontend Routes

```
/admin
├── /admin                    # Dashboard (health + activity + alerts)
├── /admin/tenants            # Tenant list
│   └── /admin/tenants/[id]   # Tenant detail (tabs: Overview, Users, Data, Audit, Settings)
├── /admin/users              # Cross-tenant user list
│   └── /admin/users/[id]     # User detail (tabs: Profile, Sessions, Audit, API Keys)
├── /admin/orders             # Cross-tenant orders
├── /admin/sync               # Marketplace sync status
├── /admin/jobs               # Background job queue
├── /admin/api-logs           # API error logs
├── /admin/search             # Global search
├── /admin/alerts             # Alert event history
│   └── /admin/alerts/rules   # Alert rule configuration
├── /admin/audit              # Admin audit log
└── /admin/settings           # System settings (existing)
```

### API Structure

```
/api/v1/admin/
├── dashboard/                # Health & activity metrics
├── tenants/                  # Tenant CRUD + actions
├── users/                    # User CRUD + actions
├── impersonation/            # Start/end impersonation
├── orders/                   # Cross-tenant order view
├── sync/                     # Sync status
├── jobs/                     # Job queue
├── api-logs/                 # Error logs
├── search/                   # Global search
├── alerts/                   # Alert events + rules
├── audit/                    # Admin audit log
└── settings/                 # System settings (existing)
```

---

## Implementation Phases

| Phase | Scope | Dependencies |
|-------|-------|--------------|
| **1** | AdminAuditLog model, tenant list/detail, suspend/reactivate | None |
| **2** | User list/detail, impersonation with ImpersonationSession | Phase 1 |
| **3** | Dashboard health/activity metrics | Phase 1 |
| **4** | Cross-tenant data views (orders, sync, jobs) | Phase 1 |
| **5** | AlertRule, AlertEvent, alerting system | Phase 3 |
| **6** | Global search | Phase 1 |

---

## Future Considerations (D: SaaS Admin)

When evolving to tiered admin permissions:

1. **AdminRole model**: Define permission levels (super, support, viewer)
2. **Scoped access**: Support staff may only see certain tenants
3. **Action restrictions**: Some actions require escalation
4. **Separate subdomain**: Extract to `admin.copio.com` with VPN/IP restrictions
5. **MFA enforcement**: Require MFA for all admin users
