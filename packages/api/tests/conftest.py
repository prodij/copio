"""Pytest configuration and fixtures."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db.base import Base
from src.db import models  # noqa: F401 - Import all models
from src.db.models import Tenant, User, Role, UserRole, UserInvite
from src.config import settings
from src.api.deps import get_db
from src.api.v1.router import api_router


def create_test_app() -> FastAPI:
    """Create a fresh FastAPI app for testing."""
    @asynccontextmanager
    async def test_lifespan(app: FastAPI):
        yield
    
    app = FastAPI(title="Copio Test", lifespan=test_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    
    # Add health endpoint (same as main app)
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "copio-api"}
    
    return app


@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Get test HTTP client with fresh database per test."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
    )
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    test_app = create_test_app()
    
    async def override_get_db():
        async with test_session_maker() as session:
            yield session
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as http_client:
        yield http_client
    
    test_app.dependency_overrides.clear()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
    )
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with test_session_maker() as session:
        yield session
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()


@pytest.fixture(scope="function")
async def client_with_db() -> AsyncGenerator[tuple[AsyncClient, AsyncSession], None]:
    """Get test HTTP client with shared database session."""
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
    )
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    test_app = create_test_app()
    session = test_session_maker()
    
    async def override_get_db():
        async with test_session_maker() as api_session:
            yield api_session
    
    test_app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(
        transport=ASGITransport(app=test_app),
        base_url="http://test",
    ) as http_client:
        yield http_client, session
    
    await session.close()
    test_app.dependency_overrides.clear()
    
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()


# =============================================================================
# Test data fixtures
# =============================================================================

@pytest.fixture(scope="function")
async def test_tenant(db_session: AsyncSession) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        id=uuid4(),
        name="Test Company",
        slug=f"test-{uuid4().hex[:8]}",
        timezone="America/Los_Angeles",
        base_currency="USD",
        settings={},
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create a test user."""
    user = User(
        id=uuid4(),
        email=f"test-{uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password_placeholder",
        tenant_id=test_tenant.id,
        first_name="Test",
        last_name="User",
        role="member",
        is_active=True,
        is_verified=True,
        is_superuser=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
async def test_role(db_session: AsyncSession, test_tenant: Tenant) -> Role:
    """Create a test role."""
    role = Role(
        id=uuid4(),
        tenant_id=test_tenant.id,
        name="Test Role",
        permissions=["*:view"],
    )
    db_session.add(role)
    await db_session.commit()
    await db_session.refresh(role)
    return role


@pytest.fixture(scope="function")
async def admin_user(db_session: AsyncSession, test_tenant: Tenant) -> User:
    """Create an admin user with all permissions."""
    user = User(
        id=uuid4(),
        email=f"admin-{uuid4().hex[:8]}@example.com",
        hashed_password="hashed_password_placeholder",
        tenant_id=test_tenant.id,
        first_name="Admin",
        last_name="User",
        role="admin",
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
