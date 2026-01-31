"""Order models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid
from src.db.models.enums import Channel, OrderStatus

if TYPE_CHECKING:
    from src.db.models.product import Product
    from src.db.models.inventory import Location


class Order(Base, TimestampMixin):
    """Order model matching Prisma Order."""

    __tablename__ = "Order"

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
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, name="Channel", create_type=False),
        nullable=False,
    )
    channel_order_id: Mapped[str] = mapped_column("channelOrderId", String, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="OrderStatus", create_type=False),
        default=OrderStatus.PENDING,
        index=True,
    )
    customer: Mapped[dict] = mapped_column(JSONB, default=dict)
    shipping_address: Mapped[dict] = mapped_column("shippingAddress", JSONB, default=dict)
    totals: Mapped[dict] = mapped_column(JSONB, default=dict)
    placed_at: Mapped[datetime] = mapped_column("placedAt", nullable=False, index=True)
    shipped_at: Mapped[datetime | None] = mapped_column("shippedAt", nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column("deliveredAt", nullable=True)

    # Relationships
    lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        # Unique constraint on channel + channelOrderId handled at DB level
        {"sqlite_autoincrement": True},
    )


class OrderLine(Base):
    """Order line model matching Prisma OrderLine."""

    __tablename__ = "OrderLine"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    order_id: Mapped[UUID] = mapped_column(
        "orderId",
        ForeignKey("Order.id"),
        nullable=False,
        index=True,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id"),
        nullable=False,
        index=True,
    )
    channel_sku: Mapped[str] = mapped_column("channelSku", String, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column("unitPrice", Numeric(10, 2), nullable=False)
    allocated_from_id: Mapped[UUID | None] = mapped_column(
        "allocatedFromId",
        ForeignKey("Location.id"),
        nullable=True,
    )

    # Relationships
    order: Mapped["Order"] = relationship("Order", back_populates="lines")
    product: Mapped["Product"] = relationship("Product", back_populates="order_lines")
    allocated_from: Mapped["Location | None"] = relationship("Location", back_populates="order_lines")
