"""API v1 router - aggregates all v1 routes."""

from fastapi import APIRouter

from src.api.v1 import velocity, sync

api_router = APIRouter()

# Include sub-routers
api_router.include_router(velocity.router, prefix="/velocity", tags=["Velocity"])
api_router.include_router(sync.router, prefix="/sync", tags=["Sync"])

# TODO: Add after auth setup
# api_router.include_router(auth.router, prefix="/auth", tags=["Auth"])
# api_router.include_router(tenants.router, prefix="/tenants", tags=["Tenants"])
