"""API v1 router - aggregates all v1 routes."""

from fastapi import APIRouter

from src.api.v1 import velocity, sync
from src.auth.routes import router as auth_router

api_router = APIRouter()

# Auth routes
api_router.include_router(auth_router, prefix="/auth", tags=["Auth"])

# Feature routes
api_router.include_router(velocity.router, prefix="/velocity", tags=["Velocity"])
api_router.include_router(sync.router, prefix="/sync", tags=["Sync"])
