# Email Verification Design

## Overview

Add configurable email verification to the registration process. When enabled, users must verify their email address before they can log in.

## Requirements

1. Email verification is **configurable** via a system setting
2. Only **superusers** (god-mode) can access and modify this setting
3. Unverified users are **blocked from logging in** entirely
4. Users can **request new verification emails** (rate-limited)
5. Verification tokens expire after **24 hours**
6. New `/admin` section visible only to superusers

## Data Model

### New `SystemSettings` Table

```python
class SystemSettings(Base, TimestampMixin):
    __tablename__ = "system_settings"

    id: Mapped[UUID]
    key: Mapped[str]           # unique, indexed
    value: Mapped[dict]        # JSON - flexible value storage
    description: Mapped[str | None]
```

Initial setting:
- `key`: `"require_email_verification"`
- `value`: `{"enabled": true}`
- `description`: `"Require users to verify email before logging in"`

## API Endpoints

### God-Mode Admin Endpoints (`/api/v1/admin/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/admin/settings` | List all system settings |
| `GET` | `/admin/settings/{key}` | Get single setting |
| `PATCH` | `/admin/settings/{key}` | Update setting value |

### Verification Endpoints (`/api/v1/auth/`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `GET` | `/auth/verify?token=xxx` | Verify email with token |
| `POST` | `/auth/resend-verification` | Request new verification email |

## Flow Logic

### Registration (`/auth/register-tenant`)

1. Create tenant + user
2. If verification required: `is_verified=False`, send verification email
3. If not required: `is_verified=True`

### Invite Acceptance (`/auth/accept-invite`)

1. Accept invite, set password, activate user
2. If verification required: keep `is_verified=False`, send email
3. If not required: set `is_verified=True`

### Login (`/auth/login`)

1. Validate credentials
2. If verification required AND `is_verified=False`: return 403
3. Else: return JWT token

### Resend Verification (`/auth/resend-verification`)

1. Accept email in request body
2. Rate limit: 1 request per email per minute
3. If user exists and `is_verified=False`: generate new token, send email
4. Always return success (don't leak user existence)

## Frontend

### New Pages

| Route | Purpose |
|-------|---------|
| `/verify-email` | Landing page for verification links |
| `/admin/settings` | God-mode system settings |

### Navigation

- Add "Admin" link in sidebar, only visible if `is_superuser=true`

### Login Page

- Handle 403 "verify email" error
- Show "Resend verification email" option

## Files

### New Files

- `packages/api/src/db/models/system_settings.py`
- `packages/api/src/api/v1/admin.py`
- `packages/api/src/services/system_settings.py`
- `packages/api/alembic/versions/xxx_add_system_settings.py`
- `packages/web/src/app/verify-email/page.tsx`
- `packages/web/src/app/admin/settings/page.tsx`
- `packages/web/src/app/admin/layout.tsx`

### Modified Files

- `packages/api/src/db/models/__init__.py`
- `packages/api/src/api/v1/router.py`
- `packages/api/src/auth/routes.py`
- `packages/api/src/auth/manager.py`
- `packages/web/src/components/sidebar.tsx`
- `packages/web/src/app/login/page.tsx`

## Implementation Order

1. Database layer - SystemSettings model + migration + seed
2. Settings service - Get/set with caching
3. Admin API - CRUD endpoints (superuser-only)
4. Auth API changes - Verify, resend, login check, registration changes
5. Frontend admin - `/admin/settings` page
6. Frontend verify - `/verify-email` page
7. Frontend login - Handle 403, resend button
8. Navigation - Admin link for superusers
