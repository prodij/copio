"""Purchase order schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.db.models.enums import POStatus, ShipmentStatus


# =============================================================================
# PO LINE
# =============================================================================

class POLineBase(BaseModel):
    """Base PO line schema."""
    
    product_id: UUID = Field(alias="productId")
    quantity_ordered: int = Field(alias="quantityOrdered")
    unit_cost: Decimal = Field(alias="unitCost")
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class POLineCreate(BaseModel):
    """Schema for creating a PO line."""
    
    product_id: UUID = Field(alias="productId")
    quantity_ordered: int = Field(alias="quantityOrdered")
    unit_cost: Decimal | None = Field(None, alias="unitCost")  # Optional, can be pulled from vendor product
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class POLineUpdate(BaseModel):
    """Schema for updating a PO line."""
    
    quantity_ordered: int | None = Field(None, alias="quantityOrdered")
    unit_cost: Decimal | None = Field(None, alias="unitCost")
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class ProductSummary(BaseModel):
    """Product summary for PO lines."""
    
    id: UUID
    sku: str
    name: str
    
    model_config = {"from_attributes": True}


class POLineRead(POLineBase):
    """Schema for reading a PO line."""
    
    id: UUID
    po_id: UUID = Field(alias="poId")
    quantity_received: int = Field(alias="quantityReceived")
    product: ProductSummary | None = None
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# PURCHASE ORDER
# =============================================================================

class PurchaseOrderBase(BaseModel):
    """Base purchase order schema."""
    
    vendor_id: UUID = Field(alias="vendorId")
    destination_id: UUID = Field(alias="destinationId")
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class PurchaseOrderCreate(PurchaseOrderBase):
    """Schema for creating a purchase order."""
    
    lines: list[POLineCreate] | None = None


class PurchaseOrderUpdate(BaseModel):
    """Schema for updating a purchase order."""
    
    notes: str | None = None
    status: POStatus | None = None
    expected_at: datetime | None = Field(None, alias="expectedAt")
    tax: Decimal | None = None
    shipping: Decimal | None = None
    
    model_config = {"populate_by_name": True}


class VendorSummary(BaseModel):
    """Vendor summary for POs."""
    
    id: UUID
    name: str
    code: str | None = None
    lead_time_days: int = Field(alias="leadTimeDays")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class LocationSummary(BaseModel):
    """Location summary for POs."""
    
    id: UUID
    name: str
    type: str
    
    model_config = {"from_attributes": True}


class PurchaseOrderRead(BaseModel):
    """Schema for reading a purchase order."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    po_number: str = Field(alias="poNumber")
    vendor_id: UUID = Field(alias="vendorId")
    destination_id: UUID = Field(alias="destinationId")
    status: POStatus
    notes: str | None = None
    
    # Financials
    subtotal: Decimal | None = None
    tax: Decimal | None = None
    shipping: Decimal | None = None
    total: Decimal | None = None
    
    # Dates
    ordered_at: datetime | None = Field(None, alias="orderedAt")
    expected_at: datetime | None = Field(None, alias="expectedAt")
    shipped_at: datetime | None = Field(None, alias="shippedAt")
    received_at: datetime | None = Field(None, alias="receivedAt")
    
    # Shipping & Tracking
    carrier: str | None = None
    tracking_number: str | None = Field(None, alias="trackingNumber")
    tracking_url: str | None = Field(None, alias="trackingUrl")
    shipment_status: ShipmentStatus | None = Field(None, alias="shipmentStatus")
    last_tracking_update: datetime | None = Field(None, alias="lastTrackingUpdate")
    
    # Follow-up
    last_contacted_at: datetime | None = Field(None, alias="lastContactedAt")
    next_follow_up_at: datetime | None = Field(None, alias="nextFollowUpAt")
    follow_up_notes: str | None = Field(None, alias="followUpNotes")
    
    # Vendor reference
    vendor_order_number: str | None = Field(None, alias="vendorOrderNumber")
    vendor_invoice_number: str | None = Field(None, alias="vendorInvoiceNumber")
    
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    vendor: VendorSummary | None = None
    destination: LocationSummary | None = None
    lines: list[POLineRead] = []
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class PurchaseOrderListItem(BaseModel):
    """PO in list response."""
    
    id: UUID
    po_number: str = Field(alias="poNumber")
    status: POStatus
    vendor: VendorSummary | None = None
    destination: LocationSummary | None = None
    total: Decimal | None = None
    expected_at: datetime | None = Field(None, alias="expectedAt")
    line_count: int = 0
    created_at: datetime = Field(alias="createdAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# RECEIVING
# =============================================================================

class ReceiveLineItem(BaseModel):
    """Line item for receiving."""
    
    line_id: UUID = Field(alias="lineId")
    quantity_received: int = Field(alias="quantityReceived")


class ReceiveItemsRequest(BaseModel):
    """Request to receive items."""
    
    lines: list[ReceiveLineItem]


# =============================================================================
# TRACKING
# =============================================================================

class TrackingUpdate(BaseModel):
    """Schema for updating tracking info."""
    
    carrier: str | None = None
    tracking_number: str | None = Field(None, alias="trackingNumber")
    tracking_url: str | None = Field(None, alias="trackingUrl")
    shipment_status: ShipmentStatus | None = Field(None, alias="shipmentStatus")
    vendor_order_number: str | None = Field(None, alias="vendorOrderNumber")
    vendor_invoice_number: str | None = Field(None, alias="vendorInvoiceNumber")
    shipped_at: datetime | None = Field(None, alias="shippedAt")
    
    model_config = {"populate_by_name": True}


# =============================================================================
# FOLLOW-UP
# =============================================================================

class FollowUpUpdate(BaseModel):
    """Schema for updating follow-up info."""
    
    last_contacted_at: datetime | None = Field(None, alias="lastContactedAt")
    next_follow_up_at: datetime | None = Field(None, alias="nextFollowUpAt")
    follow_up_notes: str | None = Field(None, alias="followUpNotes")
    
    model_config = {"populate_by_name": True}


class LogContactRequest(BaseModel):
    """Request to log a vendor contact."""
    
    notes: str | None = None
    next_follow_up_days: int | None = Field(None, alias="nextFollowUpDays")
    
    model_config = {"populate_by_name": True}


# =============================================================================
# CREATE FROM VENDOR
# =============================================================================

class CreateFromVendorRequest(BaseModel):
    """Request to create PO from vendor products."""
    
    destination_id: UUID = Field(alias="destinationId")
    product_ids: list[UUID] | None = Field(None, alias="productIds")
    notes: str | None = None
    
    model_config = {"populate_by_name": True}
