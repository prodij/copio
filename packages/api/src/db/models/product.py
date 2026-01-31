"""Product catalog models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Boolean, Integer, Numeric, Enum
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, PrismaTimestampMixin, StringUUID, generate_uuid
from src.db.models.enums import ProductType, ProductStatus

if TYPE_CHECKING:
    from src.db.models.category import ProductCategory
    from src.db.models.channel_listing import ChannelListing
    from src.db.models.inventory import StockItem
    from src.db.models.order import OrderLine
    from src.db.models.purchase_order import POLine
    from src.db.models.vendor import VendorProduct


class Product(Base, PrismaTimestampMixin):
    """Product model matching Prisma Product."""

    __tablename__ = "Product"

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
    sku: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    product_type: Mapped[ProductType] = mapped_column(
        "productType",
        Enum(ProductType, name="ProductType", create_type=False),
        default=ProductType.SIMPLE,
    )
    status: Mapped[ProductStatus] = mapped_column(
        Enum(ProductStatus, name="ProductStatus", create_type=False),
        default=ProductStatus.DRAFT,
        index=True,
    )

    # Parent/Child Variation Hierarchy
    parent_id: Mapped[UUID | None] = mapped_column(
        "parentId",
        StringUUID(),
        ForeignKey("Product.id"),
        nullable=True,
        index=True,
    )
    variation_type: Mapped[str | None] = mapped_column("variationType", String, nullable=True)
    variation_value: Mapped[str | None] = mapped_column("variationValue", String, nullable=True)

    # Core Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    brand: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    manufacturer: Mapped[str | None] = mapped_column(String, nullable=True)
    model_number: Mapped[str | None] = mapped_column("modelNumber", String, nullable=True)

    # Identifiers
    upc: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    ean: Mapped[str | None] = mapped_column(String, nullable=True)
    gtin: Mapped[str | None] = mapped_column(String, nullable=True)
    asin: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    mpn: Mapped[str | None] = mapped_column(String, nullable=True)

    # AI-Generated Listing Content
    short_description: Mapped[str | None] = mapped_column("shortDescription", Text, nullable=True)
    long_description: Mapped[str | None] = mapped_column("longDescription", Text, nullable=True)
    bullet_points: Mapped[list[str] | None] = mapped_column("bulletPoints", ARRAY(String), nullable=True)
    search_terms: Mapped[list[str] | None] = mapped_column("searchTerms", ARRAY(String), nullable=True)
    seo_title: Mapped[str | None] = mapped_column("seoTitle", String, nullable=True)
    seo_description: Mapped[str | None] = mapped_column("seoDescription", Text, nullable=True)

    # Physical Attributes
    weight_value: Mapped[Decimal | None] = mapped_column("weightValue", Numeric(10, 3), nullable=True)
    weight_unit: Mapped[str | None] = mapped_column("weightUnit", String, default="lb")
    length_value: Mapped[Decimal | None] = mapped_column("lengthValue", Numeric(10, 2), nullable=True)
    width_value: Mapped[Decimal | None] = mapped_column("widthValue", Numeric(10, 2), nullable=True)
    height_value: Mapped[Decimal | None] = mapped_column("heightValue", Numeric(10, 2), nullable=True)
    dimension_unit: Mapped[str | None] = mapped_column("dimensionUnit", String, default="in")

    # Package Dimensions
    pkg_weight_value: Mapped[Decimal | None] = mapped_column("pkgWeightValue", Numeric(10, 3), nullable=True)
    pkg_weight_unit: Mapped[str | None] = mapped_column("pkgWeightUnit", String, default="lb")
    pkg_length_value: Mapped[Decimal | None] = mapped_column("pkgLengthValue", Numeric(10, 2), nullable=True)
    pkg_width_value: Mapped[Decimal | None] = mapped_column("pkgWidthValue", Numeric(10, 2), nullable=True)
    pkg_height_value: Mapped[Decimal | None] = mapped_column("pkgHeightValue", Numeric(10, 2), nullable=True)
    pkg_dimension_unit: Mapped[str | None] = mapped_column("pkgDimensionUnit", String, default="in")

    # Compliance & Safety
    country_of_origin: Mapped[str | None] = mapped_column("countryOfOrigin", String, nullable=True)
    hazmat: Mapped[bool] = mapped_column(Boolean, default=False)
    hazmat_info: Mapped[dict | None] = mapped_column("hazmatInfo", JSONB, nullable=True)
    age_restriction: Mapped[int | None] = mapped_column("ageRestriction", Integer, nullable=True)
    certifications: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    warranty_info: Mapped[str | None] = mapped_column("warrantyInfo", String, nullable=True)

    # Pricing
    cost_price: Mapped[Decimal | None] = mapped_column("costPrice", Numeric(10, 2), nullable=True)
    msrp: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    # Relationships
    parent: Mapped["Product | None"] = relationship(
        "Product",
        remote_side="Product.id",
        back_populates="variations",
    )
    variations: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="parent",
    )
    images: Mapped[list["ProductImage"]] = relationship(
        "ProductImage",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductImage.position",
    )
    attributes: Mapped[list["ProductAttribute"]] = relationship(
        "ProductAttribute",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    categories: Mapped[list["ProductCategory"]] = relationship(
        "ProductCategory",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    listings: Mapped[list["ChannelListing"]] = relationship(
        "ChannelListing",
        back_populates="product",
    )
    stock_items: Mapped[list["StockItem"]] = relationship(
        "StockItem",
        back_populates="product",
    )
    order_lines: Mapped[list["OrderLine"]] = relationship(
        "OrderLine",
        back_populates="product",
    )
    po_lines: Mapped[list["POLine"]] = relationship(
        "POLine",
        back_populates="product",
    )
    vendors: Mapped[list["VendorProduct"]] = relationship(
        "VendorProduct",
        back_populates="product",
    )


class ProductImage(Base):
    """Product image model."""

    __tablename__ = "ProductImage"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        StringUUID(),
        ForeignKey("Product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    url: Mapped[str] = mapped_column(String, nullable=False)
    alt_text: Mapped[str | None] = mapped_column("altText", String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size_bytes: Mapped[int | None] = mapped_column("sizeBytes", Integer, nullable=True)
    mime_type: Mapped[str | None] = mapped_column("mimeType", String, default="image/jpeg")
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        default=datetime.utcnow,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="images")


class ProductAttribute(Base):
    """Product attribute model."""

    __tablename__ = "ProductAttribute"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        StringUUID(),
        ForeignKey("Product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String, nullable=False)
    group: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        "createdAt",
        default=datetime.utcnow,
    )

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="attributes")

    __table_args__ = (
        # Unique constraint on productId + name
        {"sqlite_autoincrement": True},
    )
