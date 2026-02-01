#!/usr/bin/env python3
"""Seed development database with admin role for first user.

Run: cd packages/api && python -m scripts.seed_dev
  or: cd packages/api && .venv/bin/python -m scripts.seed_dev
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.db.models.role import Role
from src.db.models.user import User
from src.db.models.user_role import UserRole
from src.db.models.tenant import Tenant


async def seed_dev_admin():
    """Create admin role and assign to first user."""
    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get first tenant
        result = await session.execute(select(Tenant).limit(1))
        tenant = result.scalar_one_or_none()
        if not tenant:
            print("❌ No tenant found. Register a tenant first.")
            return False

        # Get first user for this tenant
        result = await session.execute(
            select(User).where(User.tenant_id == tenant.id).limit(1)
        )
        user = result.scalar_one_or_none()
        if not user:
            print("❌ No user found. Register a user first.")
            return False

        print(f"📦 Tenant: {tenant.name}")
        print(f"👤 User: {user.email}")

        # Check if admin role exists
        result = await session.execute(
            select(Role).where(
                Role.tenant_id == tenant.id,
                Role.name == "Admin",
            )
        )
        admin_role = result.scalar_one_or_none()

        if not admin_role:
            # Create admin role with all permissions
            admin_role = Role(
                tenant_id=tenant.id,
                name="Admin",
                description="Full system access",
                is_system=True,
                permissions=["*:*"],
            )
            session.add(admin_role)
            await session.commit()
            print("✅ Created Admin role with *:* permissions")
        else:
            # Ensure it has full permissions
            if admin_role.permissions != ["*:*"]:
                admin_role.permissions = ["*:*"]
                await session.commit()
            print("✅ Admin role exists")

        # Check if user already has admin role
        result = await session.execute(
            select(UserRole).where(
                UserRole.user_id == user.id,
                UserRole.role_id == admin_role.id,
            )
        )
        existing = result.scalar_one_or_none()

        if not existing:
            user_role = UserRole(user_id=user.id, role_id=admin_role.id)
            session.add(user_role)
            await session.commit()
            print(f"✅ Assigned Admin role to {user.email}")
        else:
            print(f"✅ {user.email} already has Admin role")

        print("\n🎉 Dev seed complete!")
        return True

    await engine.dispose()


if __name__ == "__main__":
    success = asyncio.run(seed_dev_admin())
    sys.exit(0 if success else 1)
