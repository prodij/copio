# Multi-Tenancy Auth & Onboarding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix multi-tenancy isolation by implementing secure cookie-based auth with refresh tokens, removing dev bypass, adding API keys for CLI access, and creating onboarding flow for new tenants.

**Architecture:** Replace localStorage JWT with httpOnly cookies (access + refresh tokens). Access tokens are short-lived (15 min), refresh tokens are long-lived (7 days) and stored in DB for revocation. API keys provide CLI/integration access. New tenants go through onboarding wizard before accessing dashboard.

**Tech Stack:** FastAPI + fastapi-users (backend), Next.js 15 App Router (frontend), PostgreSQL (token/key storage)

---

## Current Problems

1. **Dev bypass breaks multi-tenancy** - Returns first user in DB when no auth header
2. **localStorage tokens** - Server Components can't access them, causing auth gaps
3. **No token revocation** - JWTs valid until expiry even after logout
4. **No onboarding** - New tenants see empty dashboard with no guidance
5. **No CLI/API access** - Can't test or integrate without browser

---

## Token Strategy

| Token | Lifetime | Storage | Purpose |
|-------|----------|---------|---------|
| Access Token | 15 minutes | httpOnly cookie `access_token` | API authentication |
| Refresh Token | 7 days | httpOnly cookie `refresh_token` | Get new access tokens |
| API Key | Until revoked | Header `Authorization: Bearer ck_...` | CLI/integration access |

---

## Task 1: Add Refresh Token Model

**Files:**
- Create: `packages/api/src/db/models/refresh_token.py`
- Modify: `packages/api/src/db/models/__init__.py`

**Step 1: Create RefreshToken model**

```python
"""Refresh token model for session management."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class RefreshToken(Base):
    """Refresh token for JWT renewal."""

    __tablename__ = "refresh_tokens"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="refresh_tokens")
```

**Step 2: Update User model to add relationship**

Add to User model:
```python
refresh_tokens: Mapped[list["RefreshToken"]] = relationship(back_populates="user", cascade="all, delete-orphan")
```

**Step 3: Export from __init__.py**

**Step 4: Create migration**

```bash
cd packages/api
alembic revision --autogenerate -m "add_refresh_tokens_table"
alembic upgrade head
```

**Step 5: Commit**

```bash
git add packages/api/src/db/models/refresh_token.py packages/api/src/db/models/__init__.py packages/api/src/db/models/user.py packages/api/alembic/versions/
git commit -m "feat(api): add RefreshToken model for session management"
```

---

## Task 2: Add API Key Model

**Files:**
- Create: `packages/api/src/db/models/api_key.py`
- Modify: `packages/api/src/db/models/__init__.py`

**Step 1: Create ApiKey model**

```python
"""API key model for CLI/integration access."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, text, ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ApiKey(Base):
    """API key for programmatic access."""

    __tablename__ = "api_keys"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    tenant_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    permissions: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=text("now()"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="api_keys")
    user: Mapped["User"] = relationship(back_populates="api_keys")
```

**Step 2: Update Tenant and User models with relationships**

**Step 3: Create migration**

```bash
alembic revision --autogenerate -m "add_api_keys_table"
alembic upgrade head
```

**Step 4: Commit**

```bash
git add packages/api/src/db/models/api_key.py packages/api/src/db/models/__init__.py packages/api/src/db/models/user.py packages/api/src/db/models/tenant.py packages/api/alembic/versions/
git commit -m "feat(api): add ApiKey model for CLI/integration access"
```

---

## Task 3: Add Onboarding Field to Tenant

**Files:**
- Modify: `packages/api/src/db/models/tenant.py`

**Step 1: Add onboarding_complete field**

```python
onboarding_complete: Mapped[bool] = mapped_column(default=False, server_default="false")
```

**Step 2: Create migration**

```bash
alembic revision --autogenerate -m "add_tenant_onboarding_complete"
alembic upgrade head
```

**Step 3: Commit**

```bash
git add packages/api/src/db/models/tenant.py packages/api/alembic/versions/
git commit -m "feat(api): add onboarding_complete field to Tenant"
```

---

## Task 4: Implement Cookie-Based Auth Backend

**Files:**
- Create: `packages/api/src/auth/cookies.py`
- Create: `packages/api/src/auth/tokens.py`
- Modify: `packages/api/src/auth/routes.py`

**Step 1: Create cookie utilities**

```python
"""Cookie utilities for auth tokens."""

from datetime import timedelta
from fastapi import Response

from src.config import settings

ACCESS_TOKEN_EXPIRE = timedelta(minutes=15)
REFRESH_TOKEN_EXPIRE = timedelta(days=7)


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    """Set httpOnly auth cookies."""
    secure = not settings.debug  # Only secure in production

    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=int(ACCESS_TOKEN_EXPIRE.total_seconds()),
        path="/",
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=int(REFRESH_TOKEN_EXPIRE.total_seconds()),
        path="/api/auth",  # Only sent to auth endpoints
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear auth cookies on logout."""
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/api/auth")
```

**Step 2: Create token utilities**

```python
"""Token generation and validation."""

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

import jwt
from passlib.hash import bcrypt

from src.config import settings

ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7


def create_access_token(user_id: UUID, tenant_id: UUID) -> str:
    """Create a short-lived JWT access token."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "exp": expire,
        "type": "access",
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> dict | None:
    """Decode and validate access token. Returns None if invalid."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("type") != "access":
            return None
        return payload
    except jwt.PyJWTError:
        return None


def create_refresh_token() -> tuple[str, str]:
    """Create refresh token. Returns (raw_token, hashed_token)."""
    raw_token = secrets.token_urlsafe(32)
    hashed = bcrypt.hash(raw_token)
    return raw_token, hashed


def verify_refresh_token(raw_token: str, hashed: str) -> bool:
    """Verify a refresh token against its hash."""
    return bcrypt.verify(raw_token, hashed)
```

**Step 3: Update auth routes with cookie-based login/logout/refresh**

Update `/api/auth/login` to set cookies instead of returning token in body.
Add `/api/auth/refresh` endpoint.
Update `/api/auth/logout` to revoke refresh token and clear cookies.

**Step 4: Commit**

```bash
git add packages/api/src/auth/cookies.py packages/api/src/auth/tokens.py packages/api/src/auth/routes.py
git commit -m "feat(api): implement cookie-based auth with refresh tokens"
```

---

## Task 5: Remove Dev Bypass and Update Dependencies

**Files:**
- Modify: `packages/api/src/api/deps.py`

**Step 1: Remove dev bypass, implement cookie-based auth**

```python
"""API dependencies for dependency injection."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_session
from src.db.models.user import User
from src.db.models.api_key import ApiKey
from src.auth.tokens import decode_access_token, verify_refresh_token
from passlib.hash import bcrypt
from datetime import datetime, timezone


async def get_db() -> AsyncSession:
    """Get database session dependency."""
    async for session in get_session():
        yield session


DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    request: Request,
    session: DbSession,
) -> User:
    """
    Get current user from access_token cookie or API key.

    Priority:
    1. API Key (Authorization: Bearer ck_...)
    2. Access token cookie
    """
    # Check for API key first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer ck_"):
        api_key = auth_header.replace("Bearer ", "")
        return await _get_user_from_api_key(session, api_key)

    # Check for access token cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    # Decode and validate token
    payload = decode_access_token(access_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    # Fetch user
    user_id = UUID(payload["sub"])
    result = await session.execute(
        select(User).where(User.id == user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


async def _get_user_from_api_key(session: AsyncSession, raw_key: str) -> User:
    """Validate API key and return associated user."""
    # Extract prefix (first 12 chars: ck_live_xxxx)
    if len(raw_key) < 12:
        raise HTTPException(status_code=401, detail="Invalid API key")

    prefix = raw_key[:12]

    # Find key by prefix
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.key_prefix == prefix,
            ApiKey.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Check expiry
    if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")

    # Verify key hash
    if not bcrypt.verify(raw_key, api_key.key_hash):
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Update last_used_at
    api_key.last_used_at = datetime.now(timezone.utc)
    await session.commit()

    # Fetch user
    result = await session.execute(
        select(User).where(User.id == api_key.user_id, User.is_active == True)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
```

**Step 2: Commit**

```bash
git add packages/api/src/api/deps.py
git commit -m "feat(api): remove dev bypass, implement cookie + API key auth"
```

---

## Task 6: Create API Keys Endpoints

**Files:**
- Create: `packages/api/src/api/v1/api_keys.py`
- Modify: `packages/api/src/api/v1/router.py`

**Step 1: Create API keys CRUD endpoints**

```python
"""API key management endpoints."""

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from passlib.hash import bcrypt
from pydantic import BaseModel
from sqlalchemy import select, func

from src.api.deps import CurrentUser, DbSession
from src.db.models.api_key import ApiKey
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class ApiKeyCreate(BaseModel):
    name: str
    expires_in_days: int | None = None  # None = never expires


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None

    class Config:
        from_attributes = True


class ApiKeyCreated(ApiKeyResponse):
    """Response when creating a key - includes full key (shown only once)."""
    key: str


@router.post("", response_model=ApiKeyCreated, status_code=201)
async def create_api_key(
    data: ApiKeyCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new API key. The full key is only shown once."""
    # Generate key: ck_live_<32 random chars>
    random_part = secrets.token_urlsafe(24)  # ~32 chars
    full_key = f"ck_live_{random_part}"
    prefix = full_key[:12]
    key_hash = bcrypt.hash(full_key)

    expires_at = None
    if data.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=data.expires_in_days)

    api_key = ApiKey(
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        name=data.name,
        key_prefix=prefix,
        key_hash=key_hash,
        expires_at=expires_at,
    )
    session.add(api_key)
    await session.commit()
    await session.refresh(api_key)

    return ApiKeyCreated(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        key=full_key,  # Only time this is returned!
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
    )


@router.get("", response_model=PaginatedResponse[ApiKeyResponse])
async def list_api_keys(
    session: DbSession,
    current_user: CurrentUser,
    page: int = 1,
    page_size: int = 25,
):
    """List all API keys for the current user."""
    query = select(ApiKey).where(
        ApiKey.user_id == current_user.id,
        ApiKey.revoked_at.is_(None),
    )

    # Count
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Fetch
    offset = (page - 1) * page_size
    result = await session.execute(
        query.order_by(ApiKey.created_at.desc()).offset(offset).limit(page_size)
    )
    keys = result.scalars().all()

    return PaginatedResponse(
        data=[ApiKeyResponse.model_validate(k) for k in keys],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_api_key(
    key_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Revoke an API key."""
    result = await session.execute(
        select(ApiKey).where(
            ApiKey.id == key_id,
            ApiKey.user_id == current_user.id,
        )
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    api_key.revoked_at = datetime.now(timezone.utc)
    await session.commit()
```

**Step 2: Register router**

**Step 3: Commit**

```bash
git add packages/api/src/api/v1/api_keys.py packages/api/src/api/v1/router.py
git commit -m "feat(api): add API key management endpoints"
```

---

## Task 7: Update Login/Logout/Refresh Routes

**Files:**
- Modify: `packages/api/src/auth/routes.py`

**Step 1: Update login to set cookies and return tenant info**

**Step 2: Add refresh endpoint**

**Step 3: Update logout to revoke refresh token and clear cookies**

**Step 4: Update register-tenant to set cookies after creation**

**Step 5: Commit**

```bash
git add packages/api/src/auth/routes.py
git commit -m "feat(api): update auth routes for cookie-based flow"
```

---

## Task 8: Update Frontend Auth Context

**Files:**
- Modify: `packages/web/src/lib/auth.tsx`

**Step 1: Remove localStorage token storage**

**Step 2: Store only user/tenant info in state (tokens are in cookies)**

**Step 3: Add refresh logic on 401 responses**

**Step 4: Update login/logout to use new endpoints**

**Step 5: Commit**

```bash
git add packages/web/src/lib/auth.tsx
git commit -m "feat(web): update auth context for cookie-based flow"
```

---

## Task 9: Update Frontend Login Page

**Files:**
- Modify: `packages/web/src/app/(auth)/login/page.tsx`

**Step 1: Update to handle new response format (user + tenant, no token)**

**Step 2: Redirect to /onboarding if tenant.onboarding_complete is false**

**Step 3: Commit**

```bash
git add packages/web/src/app/(auth)/login/page.tsx
git commit -m "feat(web): update login page for cookie auth + onboarding redirect"
```

---

## Task 10: Create Onboarding Pages

**Files:**
- Create: `packages/web/src/app/onboarding/page.tsx`
- Create: `packages/web/src/app/onboarding/layout.tsx`

**Step 1: Create onboarding layout (minimal, no sidebar)**

**Step 2: Create onboarding wizard**

Steps:
1. Company Info (reuse company settings form)
2. First Location (name, type, address)
3. Complete → mark tenant onboarding_complete, redirect to dashboard

**Step 3: Commit**

```bash
git add packages/web/src/app/onboarding/
git commit -m "feat(web): add onboarding wizard for new tenants"
```

---

## Task 11: Add Onboarding API Endpoint

**Files:**
- Modify: `packages/api/src/api/v1/company.py`

**Step 1: Add endpoint to complete onboarding**

```python
@router.post("/complete-onboarding")
async def complete_onboarding(
    session: DbSession,
    current_user: CurrentUser,
):
    """Mark tenant onboarding as complete."""
    await session.execute(
        update(Tenant)
        .where(Tenant.id == current_user.tenant_id)
        .values(onboarding_complete=True)
    )
    await session.commit()
    return {"message": "Onboarding complete"}
```

**Step 2: Commit**

```bash
git add packages/api/src/api/v1/company.py
git commit -m "feat(api): add complete-onboarding endpoint"
```

---

## Task 12: Add API Keys Settings Page

**Files:**
- Create: `packages/web/src/app/settings/api-keys/page.tsx`
- Modify: `packages/web/src/app/settings/layout.tsx`

**Step 1: Create API keys management page**

- List existing keys (name, prefix, last used, created)
- Create key dialog (shows key once with copy button)
- Revoke button per key

**Step 2: Add to settings nav**

**Step 3: Commit**

```bash
git add packages/web/src/app/settings/api-keys/ packages/web/src/app/settings/layout.tsx
git commit -m "feat(web): add API keys settings page"
```

---

## Task 13: Add Middleware for Onboarding Redirect

**Files:**
- Create: `packages/web/src/middleware.ts`

**Step 1: Create middleware to check onboarding status**

```typescript
import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip auth pages, onboarding, and API routes
  if (
    pathname.startsWith('/login') ||
    pathname.startsWith('/register') ||
    pathname.startsWith('/onboarding') ||
    pathname.startsWith('/api') ||
    pathname.startsWith('/_next')
  ) {
    return NextResponse.next();
  }

  // Check for onboarding cookie (set by login)
  const needsOnboarding = request.cookies.get('needs_onboarding')?.value === 'true';

  if (needsOnboarding) {
    return NextResponse.redirect(new URL('/onboarding', request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
```

**Step 2: Commit**

```bash
git add packages/web/src/middleware.ts
git commit -m "feat(web): add middleware for onboarding redirect"
```

---

## Task 14: Testing & Verification

**Step 1: Test registration flow**
- Register new tenant
- Verify cookies are set
- Verify redirected to onboarding

**Step 2: Test onboarding flow**
- Complete company info
- Create first location
- Verify redirected to dashboard
- Verify onboarding_complete is true

**Step 3: Test login/logout/refresh**
- Login, verify cookies set
- Wait 15+ minutes (or manually expire), verify refresh works
- Logout, verify cookies cleared and refresh token revoked

**Step 4: Test API keys**
- Create API key, copy it
- Use key with curl to hit API
- Revoke key, verify it stops working

**Step 5: Test tenant isolation**
- Login as tenant A, note data
- Login as tenant B, verify different data
- Verify no cross-tenant data leakage

**Step 6: Commit**

```bash
git commit --allow-empty -m "test: verify multi-tenancy auth flow"
```

---

## Summary

After implementation:
- No dev bypass - all requests require auth
- Cookies store tokens (httpOnly, secure, SameSite=Strict)
- 15-minute access tokens, 7-day refresh tokens
- API keys for CLI/integration access
- New tenants go through onboarding wizard
- Complete tenant isolation verified
