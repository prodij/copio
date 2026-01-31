"""Inventory schemas: Location, StockItem, StockMovement."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.db.models.enums import LocationType, MovementType, Channel


# =============================================================================
# LOCATION
# =============================================================================

class LocationBase(BaseModel):
    """Base location schema."""
    
    name: str
    type: LocationType
    channel: Channel | None = None
    address: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = Field(True, alias="isActive")
    
    model_config = {"populate_by_name": True}


class LocationCreate(LocationBase):
    """Schema for creating a location."""
    pass


class LocationUpdate(BaseModel):
    """Schema for updating a location."""
    
    name: str | None = None
    type: LocationType | None = None
    channel: Channel | None = None
    address: dict[str, Any] | None = None
    is_active: bool | None = Field(None, alias="isActive")
    
    model_config = {"populate_by_name": True}


class LocationRead(LocationBase):
    """Schema for reading a location."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# STOCK ITEM
# =============================================================================

class StockItemBase(BaseModel):
    """Base stock item schema."""
    
    product_id: UUID = Field(alias="productId")
    location_id: UUID = Field(alias="locationId")
    quantity_available: int = Field(0, alias="quantityAvailable")
    quantity_reserved: int = Field(0, alias="quantityReserved")
    quantity_inbound: int = Field(0, alias="quantityInbound")
    reorder_point: int | None = Field(None, alias="reorderPoint")
    reorder_qty: int | None = Field(None, alias="reorderQty")
    cost_basis: Decimal | None = Field(None, alias="costBasis")
    bin_location: str | None = Field(None, alias="binLocation")
    
    model_config = {"populate_by_name": True}


class StockItemCreate(BaseModel):
    """Schema for creating a stock item."""
    
    product_id: UUID = Field(alias="productId")
    location_id: UUID = Field(alias="locationId")
    quantity_available: int = Field(0, alias="quantityAvailable")
    quantity_reserved: int | None = Field(None, alias="quantityReserved")
    quantity_inbound: int | None = Field(None, alias="quantityInbound")
    reorder_point: int | None = Field(None, alias="reorderPoint")
    reorder_qty: int | None = Field(None, alias="reorderQty")
    cost_basis: Decimal | None = Field(None, alias="costBasis")
    bin_location: str | None = Field(None, alias="binLocation")
    
    model_config = {"populate_by_name": True}


class StockItemUpdate(BaseModel):
    """Schema for updating a stock item."""
    
    quantity_available: int | None = Field(None, alias="quantityAvailable")
    quantity_reserved: int | None = Field(None, alias="quantityReserved")
    quantity_inbound: int | None = Field(None, alias="quantityInbound")
    reorder_point: int | None = Field(None, alias="reorderPoint")
    reorder_qty: int | None = Field(None, alias="reorderQty")
    cost_basis: Decimal | None = Field(None, alias="costBasis")
    bin_location: str | None = Field(None, alias="binLocation")
    
    model_config = {"populate_by_name": True}


class ProductSummary(BaseModel):
    """Product summary for stock items."""
    
    id: UUID
    sku: str
    name: str
    
    model_config = {"from_attributes": True}


class StockItemRead(StockItemBase):
    """Schema for reading a stock item."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    product: ProductSummary | None = None
    location: LocationRead | None = None
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# STOCK MOVEMENT
# =============================================================================

class StockMovementBase(BaseModel):
    """Base stock movement schema."""
    
    stock_item_id: UUID = Field(alias="stockItemId")
    type: MovementType
    quantity: int
    reference: str | None = None
    notes: str | None = None
    created_by: str | None = Field(None, alias="createdBy")
    
    model_config = {"populate_by_name": True}


class StockMovementCreate(BaseModel):
    """Schema for creating a stock movement."""
    
    stock_item_id: UUID = Field(alias="stockItemId")
    type: MovementType
    quantity: int
    reference: str | None = None
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class StockMovementRead(StockMovementBase):
    """Schema for reading a stock movement."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    created_at: datetime = Field(alias="createdAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}
