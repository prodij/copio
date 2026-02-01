"""Products API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.auth.dependencies import require_permission
from src.db.models import (
    Product,
    ProductImage,
    ProductAttribute,
    ChannelListing,
    ProductType,
    ProductStatus,
)
from src.schemas.product import (
    ProductCreate,
    ProductUpdate,
    ProductRead,
    ProductListItem,
    ProductImageCreate,
    ProductImageRead,
    ProductAttributeCreate,
    ProductAttributeRead,
)
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter()


# =============================================================================
# PRODUCTS CRUD
# =============================================================================

@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("products:create")),
):
    """Create a new product."""
    # Check for duplicate SKU
    existing = await session.execute(
        select(Product).where(Product.sku == data.sku)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="SKU already exists",
        )

    # Create product
    product_data = data.model_dump(
        exclude={"images", "attributes", "channel_listings"},
        by_alias=False,
        exclude_none=True,
    )
    product_data["tenant_id"] = current_user.tenant_id
    
    product = Product(**product_data)
    session.add(product)
    await session.flush()

    # Add images
    if data.images:
        for img_data in data.images:
            img = ProductImage(
                product_id=product.id,
                **img_data.model_dump(by_alias=False),
            )
            session.add(img)

    # Add attributes
    if data.attributes:
        for attr_data in data.attributes:
            attr = ProductAttribute(
                product_id=product.id,
                **attr_data.model_dump(by_alias=False),
            )
            session.add(attr)

    # Add channel listings
    if data.channel_listings:
        for listing_data in data.channel_listings:
            listing = ChannelListing(
                product_id=product.id,
                tenant_id=current_user.tenant_id,
                **listing_data.model_dump(by_alias=False, exclude_none=True),
            )
            session.add(listing)

    await session.commit()
    await session.refresh(product)

    # Reload with relationships
    result = await session.execute(
        select(Product)
        .options(
            selectinload(Product.images),
            selectinload(Product.attributes),
            selectinload(Product.listings),
            selectinload(Product.parent),
            selectinload(Product.variations),
        )
        .where(Product.id == product.id)
    )
    return result.scalar_one()


@router.get("/", response_model=PaginatedResponse[ProductListItem])
async def list_products(
    session: DbSession,
    current_user: CurrentUser,
    type: ProductType | None = None,
    status: ProductStatus | None = Query(None),
    parent_id: str | None = Query(None, alias="parentId"),
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=1000, alias="pageSize"),
    _perm=Depends(require_permission("products:view")),
):
    """List products with pagination and filtering."""
    # Base query with tenant filter
    query = select(Product).where(Product.tenant_id == current_user.tenant_id)

    # Apply filters
    if type:
        query = query.where(Product.product_type == type)
    if status:
        query = query.where(Product.status == status)
    if parent_id == "null":
        query = query.where(Product.parent_id.is_(None))
    elif parent_id:
        query = query.where(Product.parent_id == UUID(parent_id))
    if search:
        search_filter = or_(
            Product.name.ilike(f"%{search}%"),
            Product.sku.ilike(f"%{search}%"),
            Product.brand.ilike(f"%{search}%"),
        )
        query = query.where(search_filter)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Apply pagination and ordering
    offset = (page - 1) * page_size
    query = (
        query
        .options(
            selectinload(Product.images),
            selectinload(Product.listings),
        )
        .order_by(Product.updated_at.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await session.execute(query)
    products = result.scalars().all()

    return PaginatedResponse(
        data=[ProductListItem.model_validate(p) for p in products],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(
    product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("products:view")),
):
    """Get a single product by ID."""
    result = await session.execute(
        select(Product)
        .options(
            selectinload(Product.images),
            selectinload(Product.attributes),
            selectinload(Product.listings),
            selectinload(Product.categories),
            selectinload(Product.parent),
            selectinload(Product.variations),
            selectinload(Product.vendors),
        )
        .where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


@router.patch("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: UUID,
    data: ProductUpdate,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("products:edit")),
):
    """Update a product."""
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Update fields
    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(product, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(Product)
        .options(
            selectinload(Product.images),
            selectinload(Product.attributes),
            selectinload(Product.listings),
            selectinload(Product.parent),
            selectinload(Product.variations),
        )
        .where(Product.id == product_id)
    )
    return result.scalar_one()


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    _perm=Depends(require_permission("products:delete")),
):
    """Delete a product."""
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    await session.delete(product)
    await session.commit()


# =============================================================================
# PRODUCT IMAGES
# =============================================================================

@router.post("/{product_id}/images", response_model=ProductImageRead, status_code=status.HTTP_201_CREATED)
async def add_product_image(
    product_id: UUID,
    data: ProductImageCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Add an image to a product."""
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    image = ProductImage(
        product_id=product_id,
        **data.model_dump(by_alias=False),
    )
    session.add(image)
    await session.commit()
    await session.refresh(image)
    return image


@router.delete("/{product_id}/images/{image_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a product image."""
    # Verify product belongs to tenant
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    result = await session.execute(
        select(ProductImage).where(
            ProductImage.id == image_id,
            ProductImage.product_id == product_id,
        )
    )
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Image not found",
        )

    await session.delete(image)
    await session.commit()


# =============================================================================
# PRODUCT ATTRIBUTES
# =============================================================================

@router.post("/{product_id}/attributes", response_model=ProductAttributeRead, status_code=status.HTTP_201_CREATED)
async def add_product_attribute(
    product_id: UUID,
    data: ProductAttributeCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Add an attribute to a product."""
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    # Check for duplicate attribute name
    result = await session.execute(
        select(ProductAttribute).where(
            ProductAttribute.product_id == product_id,
            ProductAttribute.name == data.name,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attribute already exists for this product",
        )

    attribute = ProductAttribute(
        product_id=product_id,
        **data.model_dump(by_alias=False),
    )
    session.add(attribute)
    await session.commit()
    await session.refresh(attribute)
    return attribute


@router.patch("/{product_id}/attributes/{attr_id}", response_model=ProductAttributeRead)
async def update_product_attribute(
    product_id: UUID,
    attr_id: UUID,
    data: ProductAttributeCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a product attribute."""
    # Verify product belongs to tenant
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    result = await session.execute(
        select(ProductAttribute).where(
            ProductAttribute.id == attr_id,
            ProductAttribute.product_id == product_id,
        )
    )
    attribute = result.scalar_one_or_none()
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attribute not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(attribute, field, value)

    await session.commit()
    await session.refresh(attribute)
    return attribute


@router.delete("/{product_id}/attributes/{attr_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product_attribute(
    product_id: UUID,
    attr_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a product attribute."""
    # Verify product belongs to tenant
    result = await session.execute(
        select(Product).where(
            Product.id == product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    result = await session.execute(
        select(ProductAttribute).where(
            ProductAttribute.id == attr_id,
            ProductAttribute.product_id == product_id,
        )
    )
    attribute = result.scalar_one_or_none()
    if not attribute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attribute not found",
        )

    await session.delete(attribute)
    await session.commit()
