"""Category and taxonomy models."""

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, String, Boolean, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base, PrismaTimestampMixin, StringUUID, generate_uuid

if TYPE_CHECKING:
    from src.db.models.product import Product


class Category(Base, PrismaTimestampMixin):
    """Category model matching Prisma Category."""

    __tablename__ = "Category"

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
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    parent_id: Mapped[UUID | None] = mapped_column(
        "parentId",
        ForeignKey("Category.id"),
        nullable=True,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Channel-specific category mappings
    amazon_browse_node: Mapped[str | None] = mapped_column("amazonBrowseNode", String, nullable=True)
    shopify_product_type: Mapped[str | None] = mapped_column("shopifyProductType", String, nullable=True)
    walmart_category_id: Mapped[str | None] = mapped_column("walmartCategoryId", String, nullable=True)
    google_category_id: Mapped[str | None] = mapped_column("googleCategoryId", String, nullable=True)

    # Relationships
    parent: Mapped["Category | None"] = relationship(
        "Category",
        remote_side="Category.id",
        back_populates="children",
    )
    children: Mapped[list["Category"]] = relationship(
        "Category",
        back_populates="parent",
    )
    products: Mapped[list["ProductCategory"]] = relationship(
        "ProductCategory",
        back_populates="category",
        cascade="all, delete-orphan",
    )


class ProductCategory(Base):
    """Product-Category junction table."""

    __tablename__ = "ProductCategory"

    id: Mapped[UUID] = mapped_column(
        StringUUID(),
        primary_key=True,
        default=generate_uuid,
    )
    product_id: Mapped[UUID] = mapped_column(
        "productId",
        ForeignKey("Product.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[UUID] = mapped_column(
        "categoryId",
        ForeignKey("Category.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column("isPrimary", Boolean, default=False)

    # Relationships
    product: Mapped["Product"] = relationship("Product", back_populates="categories")
    category: Mapped["Category"] = relationship("Category", back_populates="products")

    __table_args__ = (
        # Note: Unique constraint handled at DB level
        {"sqlite_autoincrement": True},
    )
