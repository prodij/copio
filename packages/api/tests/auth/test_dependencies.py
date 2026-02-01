# packages/api/tests/auth/test_dependencies.py
"""Tests for permission enforcement FastAPI dependencies."""
import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport

from src.auth.dependencies import require_permission, require_any_permission
from src.db.models.role import Role
from src.db.models.user_role import UserRole


def create_protected_app(db_session):
    """Create a fresh FastAPI app with permission-protected route."""
    from src.api.deps import get_db, get_current_user_with_dev_bypass
    
    app = FastAPI()
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    @app.get("/protected")
    async def protected_route(
        user = Depends(get_current_user_with_dev_bypass),
        _perm = Depends(require_permission("products:create")),
    ):
        return {"message": "success", "user": user.email}
    
    return app


@pytest.mark.asyncio
async def test_permission_granted(test_user, test_tenant, db_session):
    """Test that user with required permission can access protected route."""
    role = Role(tenant_id=test_tenant.id, name="Admin", permissions=["*:*"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    app = create_protected_app(db_session)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
        assert response.status_code == 200
        assert response.json()["user"] == test_user.email


@pytest.mark.asyncio
async def test_permission_denied(test_user, test_tenant, db_session):
    """Test that user without required permission gets 403."""
    role = Role(tenant_id=test_tenant.id, name="Viewer", permissions=["*:view"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    app = create_protected_app(db_session)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/protected")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_require_any_permission_granted(db_session, test_user, test_tenant):
    """Test require_any_permission when user has one of the required permissions."""
    from src.api.deps import get_db, get_current_user_with_dev_bypass
    
    app = FastAPI()
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    @app.get("/multi")
    async def multi_route(
        user = Depends(get_current_user_with_dev_bypass),
        _perm = Depends(require_any_permission("products:delete", "products:create")),
    ):
        return {"message": "success"}
    
    role = Role(tenant_id=test_tenant.id, name="Creator", permissions=["products:create"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/multi")
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_require_any_permission_denied(db_session, test_user, test_tenant):
    """Test require_any_permission when user has none of the required permissions."""
    from src.api.deps import get_db, get_current_user_with_dev_bypass
    
    app = FastAPI()
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    @app.get("/multi")
    async def multi_route(
        user = Depends(get_current_user_with_dev_bypass),
        _perm = Depends(require_any_permission("products:delete", "users:delete")),
    ):
        return {"message": "success"}
    
    role = Role(tenant_id=test_tenant.id, name="Viewer", permissions=["*:view"])
    db_session.add(role)
    await db_session.commit()
    
    user_role = UserRole(user_id=test_user.id, role_id=role.id)
    db_session.add(user_role)
    await db_session.commit()
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/multi")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()
