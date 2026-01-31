"""Channel listing schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from src.db.models.enums import Channel, ListingStatus, FulfillmentChannel


class ChannelListingBase(BaseModel):
    """Base channel listing schema."""
    
    product_id: UUID = Field(alias="productId")
    channel: Channel
    channel_sku: str = Field(alias="channelSku")
    
    # Identifiers
    channel_product_id: str | None = Field(None, alias="channelProductId")
    channel_variant_id: str | None = Field(None, alias="channelVariantId")
    external_id: str | None = Field(None, alias="externalId")
    
    # Content
    title: str | None = None
    description: str | None = None
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    search_terms: list[str] | None = Field(None, alias="searchTerms")
    
    # Pricing
    price: Decimal | None = None
    compare_at_price: Decimal | None = Field(None, alias="compareAtPrice")
    min_price: Decimal | None = Field(None, alias="minPrice")
    max_price: Decimal | None = Field(None, alias="maxPrice")
    
    # Fulfillment
    fulfillment_channel: FulfillmentChannel = Field(
        FulfillmentChannel.MERCHANT,
        alias="fulfillmentChannel"
    )
    handling_days: int | None = Field(None, alias="handlingDays")
    
    # Inventory
    buffer_stock: int = Field(0, alias="bufferStock")
    max_quantity: int | None = Field(None, alias="maxQuantity")
    
    # Metadata
    listing_url: str | None = Field(None, alias="listingUrl")
    channel_data: dict[str, Any] = Field(default_factory=dict, alias="channelData")
    status: ListingStatus = ListingStatus.DRAFT
    
    model_config = {"populate_by_name": True}


class ChannelListingCreate(BaseModel):
    """Schema for creating a channel listing."""
    
    product_id: UUID = Field(alias="productId")
    channel: Channel
    channel_sku: str = Field(alias="channelSku")
    
    channel_product_id: str | None = Field(None, alias="channelProductId")
    channel_variant_id: str | None = Field(None, alias="channelVariantId")
    external_id: str | None = Field(None, alias="externalId")
    
    title: str | None = None
    description: str | None = None
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    search_terms: list[str] | None = Field(None, alias="searchTerms")
    
    price: Decimal | None = None
    compare_at_price: Decimal | None = Field(None, alias="compareAtPrice")
    min_price: Decimal | None = Field(None, alias="minPrice")
    max_price: Decimal | None = Field(None, alias="maxPrice")
    
    fulfillment_channel: FulfillmentChannel | None = Field(None, alias="fulfillmentChannel")
    handling_days: int | None = Field(None, alias="handlingDays")
    
    buffer_stock: int | None = Field(None, alias="bufferStock")
    max_quantity: int | None = Field(None, alias="maxQuantity")
    
    listing_url: str | None = Field(None, alias="listingUrl")
    channel_data: dict[str, Any] | None = Field(None, alias="channelData")
    status: ListingStatus | None = None
    
    model_config = {"populate_by_name": True}


class ChannelListingUpdate(BaseModel):
    """Schema for updating a channel listing."""
    
    channel_sku: str | None = Field(None, alias="channelSku")
    channel_product_id: str | None = Field(None, alias="channelProductId")
    channel_variant_id: str | None = Field(None, alias="channelVariantId")
    external_id: str | None = Field(None, alias="externalId")
    
    title: str | None = None
    description: str | None = None
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    search_terms: list[str] | None = Field(None, alias="searchTerms")
    
    price: Decimal | None = None
    compare_at_price: Decimal | None = Field(None, alias="compareAtPrice")
    min_price: Decimal | None = Field(None, alias="minPrice")
    max_price: Decimal | None = Field(None, alias="maxPrice")
    
    fulfillment_channel: FulfillmentChannel | None = Field(None, alias="fulfillmentChannel")
    handling_days: int | None = Field(None, alias="handlingDays")
    
    buffer_stock: int | None = Field(None, alias="bufferStock")
    max_quantity: int | None = Field(None, alias="maxQuantity")
    
    listing_url: str | None = Field(None, alias="listingUrl")
    channel_data: dict[str, Any] | None = Field(None, alias="channelData")
    status: ListingStatus | None = None
    
    model_config = {"populate_by_name": True}


class ChannelListingRead(ChannelListingBase):
    """Schema for reading a channel listing."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    synced_at: datetime | None = Field(None, alias="syncedAt")
    last_error: str | None = Field(None, alias="lastError")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}
