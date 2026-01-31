"""Inventory models: Location, StockItem, StockMovement."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Boolean, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, PrismaTimestampMixin, StringUUID, generate_uuid
from src.db.models.enums import LocationType, MovementType, Channel

if TYPE_CHECKING:
    from src.db.models.product import Product
    from src.db.models.order import OrderLine
    from src.db.models.purchase_order import PurchaseOrder


class Location(Base, PrismaTimestampMixin):
    """Location model matching Prisma Location."""

    __tablename__ = "Location"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        "tenantId",
        StringUUID(),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    type: Mapped[LocationType] = mapped_column(
        Enum(LocationType, name="LocationType", create_type=False),
        nullable=False,
        index=True,
    )
    channel: Mapped[Channel | None] = mapped_column(
        Enum(Channel, name="Channel", create_type=False),
        nullable=True,
    )
    address: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column("isActive", Boolean, default=True, index=True)

    # Relationships
    stock_items: Mapped[list["StockItem"]] = relationship(
        "StockItem",
        back_populates="location",
    )
    purchase_orders: Mapped[list["PurchaseOrder"]] = relationship(
        "PurchaseOrder",
        back_populates="destination",
    )
    order_lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="allocated_from",
    )


class StockItem(Base, PrismaTimestampMixin):
    """Stock item model matching Prisma StockItem."""

    __tablename__ = "StockItem"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        "tenantId",
        StringUUID(),
        nullable=True,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id"),
        nullable=False,
    )
    location_id: Mapped[UUID] = mapped_column(
        "locationId",
        ForeignKey("Location.id"),
        nullable=False,
        index=True,
    )
    quantity_available: Mapped[int] = mapped_column("quantityAvailable", Integer, default=0, index=True)
    quantity_reserved: Mapped[int] = mapped_column("quantityReserved", Integer, default=0)
    quantity_inbound: Mapped[int] = mapped_column("quantityInbound", Integer, default=0)
    reorder_point: Mapped[int | None] = mapped_column("reorderPoint", Integer, nullable=True)
    reorder_qty: Mapped[int | None] = mapped_column("reorderQty", Integer, nullable=True)
    cost_basis: Mapped[Decimal | None] = mapped_column("costBasis", Numeric(10, 2), nullable=True)
    bin_location: Mapped[str | None] = mapped_column("binLocation", String, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="stock_items")
    location: Mapped["Location"] = relationship("Location", back_populates="stock_items")
    movements: Mapped[list["StockMovement"]] = relationship(
        "StockMovement",
        back_populates="stock_item",
    )

    __table_args__ = (
        # Unique constraint on productId + locationId handled at DB level
        {"sqlite_autoincrement": True},
    )


class StockMovement(Base):
    """Stock movement model matching Prisma StockMovement."""

    __tablename__ = "StockMovement"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    tenant_id: Mapped[UUID | None] = mapped_column(
        "tenantId",
        StringUUID(),
        nullable=True,
        index=True,
    )
    stock_item_id: Mapped[UUID] = mapped_column(
        "stockItemId",
        ForeignKey("StockItem.id"),
        nullable=False,
        index=True,
    )
    type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, name="MovementType", create_type=False),
        nullable=False,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference: Mapped[str | None] = mapped_column(String, nullable=True)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    created_by: Mapped[str | None] = mapped_column("createdBy", String, nullable=True)
    created_at: Mapped[datetime] = mapped_column("createdAt", default=datetime.utcnow, index=True)

    # Relationships
    stock_item: Mapped["StockItem"] = relationship("StockItem", back_populates="movements")
