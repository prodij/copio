"""Channel listing models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, TimestampMixin, generate_uuid
from src.db.models.enums import Channel, ListingStatus, FulfillmentChannel

if TYPE_CHECKING:
    from src.db.models.product import Product


class ChannelListing(Base, TimestampMixin):
    """Channel listing model matching Prisma ChannelListing."""

    __tablename__ = "ChannelListing"

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
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id"),
        nullable=False,
        index=True,
    )
    channel: Mapped[Channel] = mapped_column(
        Enum(Channel, name="Channel", create_type=False),
        nullable=False,
    )
    channel_sku: Mapped[str] = mapped_column("channelSku", String, nullable=False)

    # Channel-specific identifiers
    channel_product_id: Mapped[str | None] = mapped_column("channelProductId", String, nullable=True)
    channel_variant_id: Mapped[str | None] = mapped_column("channelVariantId", String, nullable=True)
    external_id: Mapped[str | None] = mapped_column("externalId", String, nullable=True)

    # Channel-specific content overrides
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullet_points: Mapped[list[str] | None] = mapped_column("bulletPoints", ARRAY(String), nullable=True)
    search_terms: Mapped[list[str] | None] = mapped_column("searchTerms", ARRAY(String), nullable=True)

    # Pricing
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    compare_at_price: Mapped[Decimal | None] = mapped_column("compareAtPrice", Numeric(10, 2), nullable=True)
    min_price: Mapped[Decimal | None] = mapped_column("minPrice", Numeric(10, 2), nullable=True)
    max_price: Mapped[Decimal | None] = mapped_column("maxPrice", Numeric(10, 2), nullable=True)

    # Fulfillment
    fulfillment_channel: Mapped[FulfillmentChannel] = mapped_column(
        "fulfillmentChannel",
        Enum(FulfillmentChannel, name="FulfillmentChannel", create_type=False),
        default=FulfillmentChannel.MERCHANT,
    )
    handling_days: Mapped[int | None] = mapped_column("handlingDays", Integer, nullable=True)

    # Inventory settings
    buffer_stock: Mapped[int] = mapped_column("bufferStock", Integer, default=0)
    max_quantity: Mapped[int | None] = mapped_column("maxQuantity", Integer, nullable=True)

    # Listing metadata
    listing_url: Mapped[str | None] = mapped_column("listingUrl", String, nullable=True)
    channel_data: Mapped[dict] = mapped_column("channelData", JSONB, default=dict)
    status: Mapped[ListingStatus] = mapped_column(
        Enum(ListingStatus, name="ListingStatus", create_type=False),
        default=ListingStatus.DRAFT,
        index=True,
    )
    synced_at: Mapped[datetime | None] = mapped_column("syncedAt", nullable=True)
    last_error: Mapped[str | None] = mapped_column("lastError", String, nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="listings")

    __table_args__ = (
        # Unique constraint on channel + channelSku handled at DB level
        {"sqlite_autoincrement": True},
    )
