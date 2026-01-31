"""Product schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from src.db.models.enums import ProductType, ProductStatus, Channel, ListingStatus


# =============================================================================
# PRODUCT IMAGE
# =============================================================================

class ProductImageBase(BaseModel):
    """Base product image schema."""
    
    url: str
    alt_text: str | None = Field(None, alias="altText")
    position: int = 0
    width: int | None = None
    height: int | None = None
    size_bytes: int | None = Field(None, alias="sizeBytes")
    mime_type: str | None = Field("image/jpeg", alias="mimeType")
    
    model_config = {"populate_by_name": True}


class ProductImageCreate(ProductImageBase):
    """Schema for creating a product image."""
    pass


class ProductImageRead(ProductImageBase):
    """Schema for reading a product image."""
    
    id: UUID
    product_id: UUID = Field(alias="productId")
    created_at: datetime = Field(alias="createdAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# PRODUCT ATTRIBUTE
# =============================================================================

class ProductAttributeBase(BaseModel):
    """Base product attribute schema."""
    
    name: str
    value: str
    group: str | None = None
    
    model_config = {"populate_by_name": True}


class ProductAttributeCreate(ProductAttributeBase):
    """Schema for creating a product attribute."""
    pass


class ProductAttributeRead(ProductAttributeBase):
    """Schema for reading a product attribute."""
    
    id: UUID
    product_id: UUID = Field(alias="productId")
    created_at: datetime = Field(alias="createdAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


# =============================================================================
# CHANNEL LISTING (embedded in product)
# =============================================================================

class ChannelListingCreate(BaseModel):
    """Schema for creating a channel listing."""
    
    channel: Channel
    channel_sku: str = Field(alias="channelSku")
    title: str | None = None
    description: str | None = None
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    price: Decimal | None = None
    channel_data: dict[str, Any] | None = Field(None, alias="channelData")
    status: ListingStatus | None = None
    
    model_config = {"populate_by_name": True}


class ChannelListingSummary(BaseModel):
    """Summary of a channel listing."""
    
    id: UUID
    channel: Channel
    status: ListingStatus
    
    model_config = {"from_attributes": True}


# =============================================================================
# PRODUCT
# =============================================================================

class ProductBase(BaseModel):
    """Base product schema."""
    
    sku: str
    name: str
    product_type: ProductType | None = Field(None, alias="productType")
    status: ProductStatus | None = None
    
    # Variation hierarchy
    parent_id: UUID | None = Field(None, alias="parentId")
    variation_type: str | None = Field(None, alias="variationType")
    variation_value: str | None = Field(None, alias="variationValue")
    
    # Identity
    brand: str | None = None
    manufacturer: str | None = None
    model_number: str | None = Field(None, alias="modelNumber")
    
    # Identifiers
    upc: str | None = None
    ean: str | None = None
    gtin: str | None = None
    asin: str | None = None
    mpn: str | None = None
    
    # AI Content
    short_description: str | None = Field(None, alias="shortDescription")
    long_description: str | None = Field(None, alias="longDescription")
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    search_terms: list[str] | None = Field(None, alias="searchTerms")
    seo_title: str | None = Field(None, alias="seoTitle")
    seo_description: str | None = Field(None, alias="seoDescription")
    
    # Physical
    weight_value: Decimal | None = Field(None, alias="weightValue")
    weight_unit: str | None = Field(None, alias="weightUnit")
    length_value: Decimal | None = Field(None, alias="lengthValue")
    width_value: Decimal | None = Field(None, alias="widthValue")
    height_value: Decimal | None = Field(None, alias="heightValue")
    dimension_unit: str | None = Field(None, alias="dimensionUnit")
    
    # Package
    pkg_weight_value: Decimal | None = Field(None, alias="pkgWeightValue")
    pkg_weight_unit: str | None = Field(None, alias="pkgWeightUnit")
    pkg_length_value: Decimal | None = Field(None, alias="pkgLengthValue")
    pkg_width_value: Decimal | None = Field(None, alias="pkgWidthValue")
    pkg_height_value: Decimal | None = Field(None, alias="pkgHeightValue")
    pkg_dimension_unit: str | None = Field(None, alias="pkgDimensionUnit")
    
    # Compliance
    country_of_origin: str | None = Field(None, alias="countryOfOrigin")
    hazmat: bool | None = None
    hazmat_info: dict[str, Any] | None = Field(None, alias="hazmatInfo")
    age_restriction: int | None = Field(None, alias="ageRestriction")
    certifications: list[str] | None = None
    warranty_info: str | None = Field(None, alias="warrantyInfo")
    
    # Pricing
    cost_price: Decimal | None = Field(None, alias="costPrice")
    msrp: Decimal | None = None
    
    model_config = {"populate_by_name": True}


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    
    images: list[ProductImageCreate] | None = None
    attributes: list[ProductAttributeCreate] | None = None
    channel_listings: list[ChannelListingCreate] | None = Field(None, alias="channelListings")


class ProductUpdate(BaseModel):
    """Schema for updating a product."""
    
    name: str | None = None
    product_type: ProductType | None = Field(None, alias="productType")
    status: ProductStatus | None = None
    
    parent_id: UUID | None = Field(None, alias="parentId")
    variation_type: str | None = Field(None, alias="variationType")
    variation_value: str | None = Field(None, alias="variationValue")
    
    brand: str | None = None
    manufacturer: str | None = None
    model_number: str | None = Field(None, alias="modelNumber")
    
    upc: str | None = None
    ean: str | None = None
    gtin: str | None = None
    asin: str | None = None
    mpn: str | None = None
    
    short_description: str | None = Field(None, alias="shortDescription")
    long_description: str | None = Field(None, alias="longDescription")
    bullet_points: list[str] | None = Field(None, alias="bulletPoints")
    search_terms: list[str] | None = Field(None, alias="searchTerms")
    seo_title: str | None = Field(None, alias="seoTitle")
    seo_description: str | None = Field(None, alias="seoDescription")
    
    weight_value: Decimal | None = Field(None, alias="weightValue")
    weight_unit: str | None = Field(None, alias="weightUnit")
    length_value: Decimal | None = Field(None, alias="lengthValue")
    width_value: Decimal | None = Field(None, alias="widthValue")
    height_value: Decimal | None = Field(None, alias="heightValue")
    dimension_unit: str | None = Field(None, alias="dimensionUnit")
    
    pkg_weight_value: Decimal | None = Field(None, alias="pkgWeightValue")
    pkg_weight_unit: str | None = Field(None, alias="pkgWeightUnit")
    pkg_length_value: Decimal | None = Field(None, alias="pkgLengthValue")
    pkg_width_value: Decimal | None = Field(None, alias="pkgWidthValue")
    pkg_height_value: Decimal | None = Field(None, alias="pkgHeightValue")
    pkg_dimension_unit: str | None = Field(None, alias="pkgDimensionUnit")
    
    country_of_origin: str | None = Field(None, alias="countryOfOrigin")
    hazmat: bool | None = None
    hazmat_info: dict[str, Any] | None = Field(None, alias="hazmatInfo")
    age_restriction: int | None = Field(None, alias="ageRestriction")
    certifications: list[str] | None = None
    warranty_info: str | None = Field(None, alias="warrantyInfo")
    
    cost_price: Decimal | None = Field(None, alias="costPrice")
    msrp: Decimal | None = None
    
    model_config = {"populate_by_name": True}
    
    @field_validator("*", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Convert empty strings to None for optional fields."""
        if v == "":
            return None
        return v


class ProductSummary(BaseModel):
    """Product summary for list views."""
    
    id: UUID
    sku: str
    name: str


class ProductRead(ProductBase):
    """Schema for reading a product."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    images: list[ProductImageRead] = []
    attributes: list[ProductAttributeRead] = []
    listings: list[ChannelListingSummary] = []
    parent: ProductSummary | None = None
    variations: list[ProductSummary] = []
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class ProductListItem(BaseModel):
    """Product item in list response."""
    
    id: UUID
    sku: str
    name: str
    brand: str | None = None
    product_type: ProductType = Field(alias="productType")
    status: ProductStatus
    images: list[ProductImageRead] = []
    listings: list[ChannelListingSummary] = []
    variation_count: int = Field(0, alias="_count_variations")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}
