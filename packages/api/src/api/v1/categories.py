"""Categories API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.db.models import Category, ProductCategory
from src.schemas.category import (
    CategoryCreate,
    CategoryUpdate,
    CategoryRead,
    CategoryWithChildren,
)
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter()


@router.post("/", response_model=CategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    data: CategoryCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new category."""
    # Check for duplicate slug
    existing = await session.execute(
        select(Category).where(Category.slug == data.slug)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Category with this slug already exists",
        )

    # Verify parent exists if provided
    if data.parent_id:
        parent = await session.execute(
            select(Category).where(Category.id == data.parent_id)
        )
        if not parent.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Parent category not found",
            )

    category = Category(
        tenant_id=current_user.tenant_id,
        **data.model_dump(by_alias=False),
    )
    session.add(category)
    await session.commit()
    await session.refresh(category)
    return category


@router.get("/", response_model=PaginatedResponse[CategoryRead])
async def list_categories(
    session: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500, alias="pageSize"),
):
    """List all categories for the tenant."""
    # Count total
    count_result = await session.execute(
        select(func.count(Category.id)).where(
            Category.tenant_id == current_user.tenant_id
        )
    )
    total = count_result.scalar() or 0

    # Fetch paginated results
    offset = (page - 1) * page_size
    result = await session.execute(
        select(Category)
        .where(Category.tenant_id == current_user.tenant_id)
        .order_by(Category.name)
        .offset(offset)
        .limit(page_size)
    )
    categories = result.scalars().all()

    return PaginatedResponse(
        data=categories,
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size if total > 0 else 0,
        ),
    )


@router.get("/tree", response_model=list[CategoryWithChildren])
async def get_category_tree(
    session: DbSession,
    current_user: CurrentUser,
):
    """Get category tree (hierarchical)."""
    result = await session.execute(
        select(Category)
        .where(
            Category.tenant_id == current_user.tenant_id,
            Category.parent_id.is_(None),
        )
        .options(selectinload(Category.children).selectinload(Category.children))
        .order_by(Category.name)
    )
    return result.scalars().all()


@router.get("/{category_id}", response_model=CategoryRead)
async def get_category(
    category_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single category."""
    result = await session.execute(
        select(Category).where(
            Category.id == category_id,
            Category.tenant_id == current_user.tenant_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


@router.patch("/{category_id}", response_model=CategoryRead)
async def update_category(
    category_id: UUID,
    data: CategoryUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a category."""
    result = await session.execute(
        select(Category).where(
            Category.id == category_id,
            Category.tenant_id == current_user.tenant_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Check for duplicate slug if changing
    if data.slug and data.slug != category.slug:
        existing = await session.execute(
            select(Category).where(
                Category.slug == data.slug,
                Category.id != category_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Category with this slug already exists",
            )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(category, field, value)

    await session.commit()
    await session.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(
    category_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a category."""
    result = await session.execute(
        select(Category).where(
            Category.id == category_id,
            Category.tenant_id == current_user.tenant_id,
        )
    )
    category = result.scalar_one_or_none()
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    # Check for child categories
    children = await session.execute(
        select(Category).where(Category.parent_id == category_id)
    )
    if children.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete category with children",
        )

    await session.delete(category)
    await session.commit()
