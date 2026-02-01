"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.main import app
from src.db.session import engine
from src.db.base import Base
from src.db import models  # Import all models to register them with Base
from src.db.models import Tenant, User, Role, UserRole, UserInvite
from src.config import settings


@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    """Get test HTTP client."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    # Dispose engine connections after each test to avoid event loop issues
    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a test database session with automatic rollback."""
    # Create a fresh engine for this test to avoid event loop issues
    test_engine = create_async_engine(
        settings.async_database_url,
        echo=False,
        pool_pre_ping=True,
    )
    test_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with test_session_maker() as session:
        yield session
        await session.rollback()
    
    # Drop all tables after test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await test_engine.dispose()


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
