"""Pydantic schemas for velocity endpoints."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ListingVelocityResponse(BaseModel):
    """Response schema for listing velocity."""
    
    listing_id: UUID
    title: str
    channel: str
    velocity_1d: Decimal
    velocity_7d: Decimal
    velocity_30d: Decimal
    trend_7d_30d: Decimal | None
    health_status: str  # 'healthy' | 'declining' | 'dead_stock' | 'accelerating'
    calculated_at: datetime
    
    class Config:
        from_attributes = True


class SkuConsumptionResponse(BaseModel):
    """Response schema for SKU consumption."""
    
    sku_id: UUID
    sku: str
    name: str
    consumption_1d: Decimal
    consumption_7d: Decimal
    consumption_30d: Decimal
    on_hand_qty: int
    days_of_stock: Decimal | None
    reorder_urgency: str | None  # 'ok' | 'low' | 'critical' | 'out'
    calculated_at: datetime
    
    class Config:
        from_attributes = True


class VelocityDashboardResponse(BaseModel):
    """Response schema for velocity dashboard."""
    
    total_listings: int
    healthy: int
    accelerating: int
    declining: int
    dead_stock: int
    top_movers: list[ListingVelocityResponse]
    problem_listings: list[ListingVelocityResponse]


class VelocityFactorCreate(BaseModel):
    """Schema for creating a velocity factor."""
    
    scope_type: str  # 'listing' | 'channel' | 'tenant'
    listing_id: UUID | None = None
    channel: str | None = None
    factor_type: str  # 'suppression' | 'promotion' | 'advertising' | etc.
    direction: str  # 'increase' | 'decrease' | 'mixed'
    name: str
    description: str | None = None
    effective_from: datetime
    effective_to: datetime | None = None
    metadata: dict = {}


class VelocityFactorResponse(VelocityFactorCreate):
    """Response schema for velocity factor."""
    
    id: UUID
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
