"""Vendor models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Boolean, Integer, Float, Numeric, Enum, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid
from src.db.models.enums import VendorTier, ContactRole, AddressType, DocumentType

if TYPE_CHECKING:
    from src.db.models.product import Product
    from src.db.models.purchase_order import PurchaseOrder


class Vendor(Base, TimestampMixin):
    """Vendor model matching Prisma Vendor."""

    __tablename__ = "Vendor"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        "tenantId",
        PG_UUID(as_uuid=True),
        nullable=True,
        index=True,
    )

    # Company Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    legal_name: Mapped[str | None] = mapped_column("legalName", String, nullable=True)
    code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True)
    tax_id: Mapped[str | None] = mapped_column("taxId", String, nullable=True)
    website: Mapped[str | None] = mapped_column(String, nullable=True)

    # Classification
    tier: Mapped[VendorTier] = mapped_column(
        Enum(VendorTier, name="VendorTier", create_type=False),
        default=VendorTier.STANDARD,
        index=True,
    )
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)

    # Legacy address fields
    address: Mapped[dict] = mapped_column(JSONB, default=dict)
    billing_address: Mapped[dict] = mapped_column("billingAddress", JSONB, default=dict)

    # Ordering & Terms
    lead_time_days: Mapped[int] = mapped_column("leadTimeDays", Integer, default=14)
    min_order_value: Mapped[Decimal | None] = mapped_column("minOrderValue", Numeric(10, 2), nullable=True)
    payment_terms: Mapped[str | None] = mapped_column("paymentTerms", String, nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column("creditLimit", Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String, default="USD")

    # Account Management
    account_manager_name: Mapped[str | None] = mapped_column("accountManagerName", String, nullable=True)
    account_manager_email: Mapped[str | None] = mapped_column("accountManagerEmail", String, nullable=True)
    preferred_contact_method: Mapped[str | None] = mapped_column("preferredContactMethod", String, nullable=True)

    # Contract & Compliance
    contract_start_date: Mapped[datetime | None] = mapped_column("contractStartDate", nullable=True)
    contract_end_date: Mapped[datetime | None] = mapped_column("contractEndDate", nullable=True, index=True)
    insurance_expiry: Mapped[datetime | None] = mapped_column("insuranceExpiry", nullable=True)
    w9_on_file: Mapped[bool] = mapped_column("w9OnFile", Boolean, default=False)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column("internalNotes", Text, nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True, index=True)
    onboarded_at: Mapped[datetime | None] = mapped_column("onboardedAt", nullable=True)

    # Relationships
    addresses: Mapped[list["VendorAddress"]] = relationship(
        "VendorAddress",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    contacts: Mapped[list["VendorContact"]] = relationship(
        "VendorContact",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["VendorDocument"]] = relationship(
        "VendorDocument",
        back_populates="vendor",
        cascade="all, delete-orphan",
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="vendor",
    )
    products: Mapped[list["VendorProduct"]] = relationship(
        "VendorProduct",
        back_populates="vendor",
    )


class VendorContact(Base, TimestampMixin):
    """Vendor contact model matching Prisma VendorContact."""

    __tablename__ = "VendorContact"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    vendor_id: Mapped[UUID] = mapped_column(
        "vendorId",
        ForeignKey("Vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Contact Info
    name: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)
    mobile: Mapped[str | None] = mapped_column(String, nullable=True)

    # Role/Purpose
    role: Mapped[ContactRole] = mapped_column(
        Enum(ContactRole, name="ContactRole", create_type=False),
        default=ContactRole.GENERAL,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column("isPrimary", Boolean, default=False)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="contacts")


class VendorAddress(Base, TimestampMixin):
    """Vendor address model matching Prisma VendorAddress."""

    __tablename__ = "VendorAddress"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    vendor_id: Mapped[UUID] = mapped_column(
        "vendorId",
        ForeignKey("Vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Address Type
    type: Mapped[AddressType] = mapped_column(
        Enum(AddressType, name="AddressType", create_type=False),
        default=AddressType.WAREHOUSE,
        index=True,
    )
    label: Mapped[str | None] = mapped_column(String, nullable=True)
    is_primary: Mapped[bool] = mapped_column("isPrimary", Boolean, default=False)

    # Address Fields
    street1: Mapped[str] = mapped_column(String, nullable=False)
    street2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    state: Mapped[str | None] = mapped_column(String, nullable=True)
    postal_code: Mapped[str | None] = mapped_column("postalCode", String, nullable=True)
    country: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Geolocation
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)

    # Tax & Trade
    tax_jurisdiction: Mapped[str | None] = mapped_column("taxJurisdiction", String, nullable=True)
    ftz_zone: Mapped[str | None] = mapped_column("ftzZone", String, nullable=True)
    port_of_entry: Mapped[str | None] = mapped_column("portOfEntry", String, nullable=True)

    # Contact for this location
    contact_name: Mapped[str | None] = mapped_column("contactName", String, nullable=True)
    contact_phone: Mapped[str | None] = mapped_column("contactPhone", String, nullable=True)
    contact_email: Mapped[str | None] = mapped_column("contactEmail", String, nullable=True)

    # Operational
    shipping_notes: Mapped[str | None] = mapped_column("shippingNotes", Text, nullable=True)

    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="addresses")


class VendorDocument(Base, TimestampMixin):
    """Vendor document model matching Prisma VendorDocument."""

    __tablename__ = "VendorDocument"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    vendor_id: Mapped[UUID] = mapped_column(
        "vendorId",
        ForeignKey("Vendor.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Document Info
    type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="DocumentType", create_type=False),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Storage (MinIO)
    bucket: Mapped[str] = mapped_column(String, default="vendor-documents")
    object_key: Mapped[str] = mapped_column("objectKey", String, nullable=False)
    mime_type: Mapped[str] = mapped_column("mimeType", String, nullable=False)
    size_bytes: Mapped[int] = mapped_column("sizeBytes", Integer, nullable=False)

    # Metadata
    expires_at: Mapped[datetime | None] = mapped_column("expiresAt", nullable=True, index=True)
    version: Mapped[str | None] = mapped_column(String, nullable=True)

    # Upload tracking
    uploaded_by: Mapped[str | None] = mapped_column("uploadedBy", String, nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column("uploadedAt", default=datetime.utcnow)

    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="documents")


class VendorProduct(Base, TimestampMixin):
    """Vendor-Product relationship model matching Prisma VendorProduct."""

    __tablename__ = "VendorProduct"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    vendor_id: Mapped[UUID] = mapped_column(
        "vendorId",
        ForeignKey("Vendor.id"),
        nullable=False,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id"),
        nullable=False,
        index=True,
    )

    # Vendor's identification
    vendor_sku: Mapped[str] = mapped_column("vendorSku", String, nullable=False)
    vendor_product_name: Mapped[str | None] = mapped_column("vendorProductName", String, nullable=True)

    # Pricing
    unit_cost: Mapped[Decimal] = mapped_column("unitCost", Numeric(10, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="USD")

    # Ordering constraints
    min_order_qty: Mapped[int] = mapped_column("minOrderQty", Integer, default=1)
    order_multiple: Mapped[int] = mapped_column("orderMultiple", Integer, default=1)
    case_pack_qty: Mapped[int | None] = mapped_column("casePackQty", Integer, nullable=True)

    # Lead time
    lead_time_days: Mapped[int | None] = mapped_column("leadTimeDays", Integer, nullable=True)

    # Status
    is_preferred: Mapped[bool] = mapped_column("isPreferred", Boolean, default=False, index=True)
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True)

    # Timestamps
    last_ordered_at: Mapped[datetime | None] = mapped_column("lastOrderedAt", nullable=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="products")
    product: Mapped["Product"] = relationship("Product", back_populates="vendors")

    __table_args__ = (
        # Unique constraints handled at DB level
        {"sqlite_autoincrement": True},
    )
