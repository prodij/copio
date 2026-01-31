"""Purchase order models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid
from src.db.models.enums import POStatus, ShipmentStatus

if TYPE_CHECKING:
    from src.db.models.vendor import Vendor
    from src.db.models.inventory import Location
    from src.db.models.product import Product


class PurchaseOrder(Base, TimestampMixin):
    """Purchase order model matching Prisma PurchaseOrder."""

    __tablename__ = "PurchaseOrder"

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
    po_number: Mapped[str] = mapped_column("poNumber", String, unique=True, nullable=False, index=True)
    vendor_id: Mapped[UUID] = mapped_column(
        "vendorId",
        ForeignKey("Vendor.id"),
        nullable=False,
        index=True,
    )
    destination_id: Mapped[UUID] = mapped_column(
        "destinationId",
        ForeignKey("Location.id"),
        nullable=False,
    )
    status: Mapped[POStatus] = mapped_column(
        Enum(POStatus, name="POStatus", create_type=False),
        default=POStatus.DRAFT,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Financials
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    tax: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    shipping: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Dates
    ordered_at: Mapped[datetime | None] = mapped_column("orderedAt", nullable=True)
    expected_at: Mapped[datetime | None] = mapped_column("expectedAt", nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column("shippedAt", nullable=True)
    received_at: Mapped[datetime | None] = mapped_column("receivedAt", nullable=True)

    # Shipping & Tracking
    carrier: Mapped[str | None] = mapped_column(String, nullable=True)
    tracking_number: Mapped[str | None] = mapped_column("trackingNumber", String, nullable=True)
    tracking_url: Mapped[str | None] = mapped_column("trackingUrl", String, nullable=True)
    shipment_status: Mapped[ShipmentStatus | None] = mapped_column(
        "shipmentStatus",
        Enum(ShipmentStatus, name="ShipmentStatus", create_type=False),
        nullable=True,
        index=True,
    )
    last_tracking_update: Mapped[datetime | None] = mapped_column("lastTrackingUpdate", nullable=True)

    # Vendor Follow-up
    last_contacted_at: Mapped[datetime | None] = mapped_column("lastContactedAt", nullable=True)
    next_follow_up_at: Mapped[datetime | None] = mapped_column("nextFollowUpAt", nullable=True, index=True)
    follow_up_notes: Mapped[str | None] = mapped_column("followUpNotes", Text, nullable=True)

    # Vendor reference
    vendor_order_number: Mapped[str | None] = mapped_column("vendorOrderNumber", String, nullable=True)
    vendor_invoice_number: Mapped[str | None] = mapped_column("vendorInvoiceNumber", String, nullable=True)

    # Relationships
    vendor: Mapped["Vendor"] = relationship("Vendor", back_populates="purchase_orders")
    destination: Mapped["Location"] = relationship("Location", back_populates="purchase_orders")
    lines: Mapped[list["POLine"]] = relationship(
        "POLine",
        back_populates="purchase_order",
        cascade="all, delete-orphan",
    )


class POLine(Base):
    """Purchase order line model matching Prisma POLine."""

    __tablename__ = "POLine"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    po_id: Mapped[UUID] = mapped_column(
        "poId",
        ForeignKey("PurchaseOrder.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id"),
        nullable=False,
        index=True,
    )
    quantity_ordered: Mapped[int] = mapped_column("quantityOrdered", Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column("quantityReceived", Integer, default=0)
    unit_cost: Mapped[Decimal] = mapped_column("unitCost", Numeric(10, 2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    purchase_order: Mapped["PurchaseOrder"] = relationship("PurchaseOrder", back_populates="lines")
    product: Mapped["Product"] = relationship("Product", back_populates="po_lines")
