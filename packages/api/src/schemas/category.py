"""Category schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CategoryBase(BaseModel):
    """Base category schema."""
    
    name: str
    slug: str
    parent_id: UUID | None = Field(None, alias="parentId")
    description: str | None = None
    
    # Channel mappings
    amazon_browse_node: str | None = Field(None, alias="amazonBrowseNode")
    shopify_product_type: str | None = Field(None, alias="shopifyProductType")
    walmart_category_id: str | None = Field(None, alias="walmartCategoryId")
    google_category_id: str | None = Field(None, alias="googleCategoryId")
    
    model_config = {"populate_by_name": True}


class CategoryCreate(CategoryBase):
    """Schema for creating a category."""
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating a category."""
    
    name: str | None = None
    slug: str | None = None
    parent_id: UUID | None = Field(None, alias="parentId")
    description: str | None = None
    amazon_browse_node: str | None = Field(None, alias="amazonBrowseNode")
    shopify_product_type: str | None = Field(None, alias="shopifyProductType")
    walmart_category_id: str | None = Field(None, alias="walmartCategoryId")
    google_category_id: str | None = Field(None, alias="googleCategoryId")
    
    model_config = {"populate_by_name": True}


class CategoryRead(CategoryBase):
    """Schema for reading a category."""
    
    id: UUID
    tenant_id: UUID | None = Field(None, alias="tenantId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
    
    model_config = {"from_attributes": True, "populate_by_name": True}


class CategoryWithChildren(CategoryRead):
    """Category with children."""
    
    children: list["CategoryWithChildren"] = []


class ProductCategoryBase(BaseModel):
    """Base product-category association schema."""
    
    product_id: UUID = Field(alias="productId")
    category_id: UUID = Field(alias="categoryId")
    is_primary: bool = Field(False, alias="isPrimary")
    
    model_config = {"populate_by_name": True}


class ProductCategoryCreate(BaseModel):
    """Schema for creating a product-category association."""
    
    category_id: UUID = Field(alias="categoryId")
    is_primary: bool = Field(False, alias="isPrimary")
    
    model_config = {"populate_by_name": True}


class ProductCategoryRead(ProductCategoryBase):
    """Schema for reading a product-category association."""
    
    id: UUID
    category: CategoryRead | None = None
    
    model_config = {"from_attributes": True, "populate_by_name": True}
