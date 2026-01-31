"""Vendor schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr

from src.db.models.enums import (
    VendorTier,
    ContactRole,
    AddressType,
    DocumentType,
)


# =============================================================================
# VENDOR CONTACT
# =============================================================================

class VendorContactBase(BaseModel):
    """Base vendor contact schema."""
    
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    role: ContactRole = ContactRole.GENERAL
    is_primary: bool = Field(False, alias="isPrimary")
    notes: str | None = None
    is_active: bool = Field(True, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorContactCreate(BaseModel):
    """Schema for creating a vendor contact."""
    
    name: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    role: ContactRole = ContactRole.GENERAL
    is_primary: bool = Field(False, alias="isPrimary")
    notes: str | None = None
    
    model_config = {"populate_by_name": True}


class VendorContactUpdate(BaseModel):
    """Schema for updating a vendor contact."""
    
    name: str | None = None
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    mobile: str | None = None
    role: ContactRole | None = None
    is_primary: bool | None = Field(None, alias="isPrimary")
    notes: str | None = None
    is_active: bool | None = Field(None, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorContactRead(VendorContactBase):
    """Schema for reading a vendor contact."""
    
    id: UUID
    vendor_id: UUID = Field(alias="vendorId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# VENDOR ADDRESS
# =============================================================================

class VendorAddressBase(BaseModel):
    """Base vendor address schema."""
    
    type: AddressType = AddressType.WAREHOUSE
    label: str | None = None
    is_primary: bool = Field(False, alias="isPrimary")
    
    street1: str
    street2: str | None = None
    city: str
    state: str | None = None
    postal_code: str | None = Field(None, alias="postalCode")
    country: str
    
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    
    tax_jurisdiction: str | None = Field(None, alias="taxJurisdiction")
    ftz_zone: str | None = Field(None, alias="ftzZone")
    port_of_entry: str | None = Field(None, alias="portOfEntry")
    
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")
    
    shipping_notes: str | None = Field(None, alias="shippingNotes")
    is_active: bool = Field(True, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorAddressCreate(VendorAddressBase):
    """Schema for creating a vendor address."""
    pass


class VendorAddressUpdate(BaseModel):
    """Schema for updating a vendor address."""
    
    type: AddressType | None = None
    label: str | None = None
    is_primary: bool | None = Field(None, alias="isPrimary")
    
    street1: str | None = None
    street2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = Field(None, alias="postalCode")
    country: str | None = None
    
    latitude: float | None = None
    longitude: float | None = None
    timezone: str | None = None
    
    tax_jurisdiction: str | None = Field(None, alias="taxJurisdiction")
    ftz_zone: str | None = Field(None, alias="ftzZone")
    port_of_entry: str | None = Field(None, alias="portOfEntry")
    
    contact_name: str | None = Field(None, alias="contactName")
    contact_phone: str | None = Field(None, alias="contactPhone")
    contact_email: str | None = Field(None, alias="contactEmail")
    
    shipping_notes: str | None = Field(None, alias="shippingNotes")
    is_active: bool | None = Field(None, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorAddressRead(VendorAddressBase):
    """Schema for reading a vendor address."""
    
    id: UUID
    vendor_id: UUID = Field(alias="vendorId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# VENDOR DOCUMENT
# =============================================================================

class VendorDocumentBase(BaseModel):
    """Base vendor document schema."""
    
    type: DocumentType
    name: str
    description: str | None = None
    bucket: str = "vendor-documents"
    object_key: str = Field(alias="objectKey")
    mime_type: str = Field(alias="mimeType")
    size_bytes: int = Field(alias="sizeBytes")
    expires_at: datetime | None = Field(None, alias="expiresAt")
    version: str | None = None
    
    model_config = {"populate_by_name": True}


class VendorDocumentCreate(VendorDocumentBase):
    """Schema for creating a vendor document."""
    pass


class VendorDocumentUpdate(BaseModel):
    """Schema for updating a vendor document."""
    
    name: str | None = None
    description: str | None = None
    expires_at: datetime | None = Field(None, alias="expiresAt")
    version: str | None = None
    is_active: bool | None = Field(None, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorDocumentRead(VendorDocumentBase):
    """Schema for reading a vendor document."""
    
    id: UUID
    vendor_id: UUID = Field(alias="vendorId")
    uploaded_by: str | None = Field(None, alias="uploadedBy")
    uploaded_at: datetime = Field(alias="uploadedAt")
    is_active: bool = Field(alias="isActive")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# VENDOR PRODUCT
# =============================================================================

class VendorProductBase(BaseModel):
    """Base vendor-product schema."""
    
    vendor_sku: str = Field(alias="vendorSku")
    vendor_product_name: str | None = Field(None, alias="vendorProductName")
    unit_cost: Decimal = Field(alias="unitCost")
    currency: str = "USD"
    min_order_qty: int = Field(1, alias="minOrderQty")
    order_multiple: int = Field(1, alias="orderMultiple")
    case_pack_qty: int | None = Field(None, alias="casePackQty")
    lead_time_days: int | None = Field(None, alias="leadTimeDays")
    is_preferred: bool = Field(False, alias="isPreferred")
    is_active: bool = Field(True, alias="isActive")
    
    model_config = {"populate_by_name": True}


class VendorProductCreate(BaseModel):
    """Schema for creating a vendor-product relationship."""
    
    product_id: UUID = Field(alias="productId")
    vendor_sku: str = Field(alias="vendorSku")
    vendor_product_name: str | None = Field(None, alias="vendorProductName")
    unit_cost: Decimal = Field(alias="unitCost")
    currency: str = "USD"
    min_order_qty: int = Field(1, alias="minOrderQty")
    order_multiple: int = Field(1, alias="orderMultiple")
    case_pack_qty: int | None = Field(None, alias="casePackQty")
    lead_time_days: int | None = Field(None, alias="leadTimeDays")
    is_preferred: bool = Field(False, alias="isPreferred")
    
    model_config = {"populate_by_name": True}


class VendorProductUpdate(BaseModel):
    """Schema for updating a vendor-product relationship."""
    
    vendor_sku: str | None = Field(None, alias="vendorSku")
    vendor_product_name: str | None = Field(None, alias="vendorProductName")
    unit_cost: Decimal | None = Field(None, alias="unitCost")
    currency: str | None = None
    min_order_qty: int | None = Field(None, alias="minOrderQty")
    order_multiple: int | None = Field(None, alias="orderMultiple")
    case_pack_qty: int | None = Field(None, alias="casePackQty")
    lead_time_days: int | None = Field(None, alias="leadTimeDays")
    is_preferred: bool | None = Field(None, alias="isPreferred")
    is_active: bool | None = Field(None, alias="isActive")
    
    model_config = {"populate_by_name": True}


class ProductSummary(BaseModel):
    """Product summary for vendor products."""
    
    id: UUID
    sku: str
    name: str
    
    model_config = {"from_attributes": True}


class VendorProductRead(VendorProductBase):
    """Schema for reading a vendor-product relationship."""
    
    id: UUID
    vendor_id: UUID = Field(alias="vendorId")
    product_id: UUID = Field(alias="productId")
    last_ordered_at: datetime | None = Field(None, alias="lastOrderedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    product: ProductSummary | None = None
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# VENDOR
# =============================================================================

class VendorBase(BaseModel):
    """Base vendor schema."""
    
    name: str
    legal_name: str | None = Field(None, alias="legalName")
    code: str | None = None
    tax_id: str | None = Field(None, alias="taxId")
    website: str | None = None
    
    tier: VendorTier = VendorTier.STANDARD
    category: str | None = None
    tags: list[str] | None = None
    
    address: dict[str, Any] = Field(default_factory=dict)
    billing_address: dict[str, Any] = Field(default_factory=dict, alias="billingAddress")
    
    lead_time_days: int = Field(14, alias="leadTimeDays")
    min_order_value: Decimal | None = Field(None, alias="minOrderValue")
    payment_terms: str | None = Field(None, alias="paymentTerms")
    credit_limit: Decimal | None = Field(None, alias="creditLimit")
    currency: str = "USD"
    
    account_manager_name: str | None = Field(None, alias="accountManagerName")
    account_manager_email: str | None = Field(None, alias="accountManagerEmail")
    preferred_contact_method: str | None = Field(None, alias="preferredContactMethod")
    
    contract_start_date: datetime | None = Field(None, alias="contractStartDate")
    contract_end_date: datetime | None = Field(None, alias="contractEndDate")
    insurance_expiry: datetime | None = Field(None, alias="insuranceExpiry")
    w9_on_file: bool = Field(False, alias="w9OnFile")
    
    notes: str | None = None
    internal_notes: str | None = Field(None, alias="internalNotes")
    
    model_config = {"populate_by_name": True}


class VendorCreate(VendorBase):
    """Schema for creating a vendor."""
    pass


class VendorUpdate(BaseModel):
    """Schema for updating a vendor."""
    
    name: str | None = None
    legal_name: str | None = Field(None, alias="legalName")
    code: str | None = None
    tax_id: str | None = Field(None, alias="taxId")
    website: str | None = None
    
    tier: VendorTier | None = None
    category: str | None = None
    tags: list[str] | None = None
    
    address: dict[str, Any] | None = None
    billing_address: dict[str, Any] | None = Field(None, alias="billingAddress")
    
    lead_time_days: int | None = Field(None, alias="leadTimeDays")
    min_order_value: Decimal | None = Field(None, alias="minOrderValue")
    payment_terms: str | None = Field(None, alias="paymentTerms")
    credit_limit: Decimal | None = Field(None, alias="creditLimit")
    currency: str | None = None
    
    account_manager_name: str | None = Field(None, alias="accountManagerName")
    account_manager_email: str | None = Field(None, alias="accountManagerEmail")
    preferred_contact_method: str | None = Field(None, alias="preferredContactMethod")
    
    contract_start_date: datetime | None = Field(None, alias="contractStartDate")
    contract_end_date: datetime | None = Field(None, alias="contractEndDate")
    insurance_expiry: datetime | None = Field(None, alias="insuranceExpiry")
    w9_on_file: bool | None = Field(None, alias="w9OnFile")
    
    notes: str | None = None
    internal_notes: str | None = Field(None, alias="internalNotes")
    
    is_active: bool | None = Field(None, alias="isActive")
    onboarded_at: datetime | None = Field(None, alias="onboardedAt")
    
    model_config = {"populate_by_name": True}


class VendorRead(VendorBase):
    """Schema for reading a vendor."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    is_active: bool = Field(alias="isActive")
    onboarded_at: datetime | None = Field(None, alias="onboardedAt")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    contacts: list[VendorContactRead] = []
    addresses: list[VendorAddressRead] = []
    documents: list[VendorDocumentRead] = []
    products: list[VendorProductRead] = []
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class VendorListItem(BaseModel):
    """Vendor in list response."""
    
    id: UUID
    name: str
    code: str | None = None
    tier: VendorTier
    is_active: bool = Field(alias="isActive")
    lead_time_days: int = Field(alias="leadTimeDays")
    contacts: list[VendorContactRead] = []
    product_count: int = 0
    po_count: int = 0
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class VendorStatsSummary(BaseModel):
    """Vendor stats summary."""
    
    total: int
    by_tier: dict[str, int] = Field(alias="byTier")
    contracts_expiring_soon: int = Field(alias="contractsExpiringSoon")
    
    model_config = {"populate_by_name": True}
