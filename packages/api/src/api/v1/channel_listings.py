"""Channel listings API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.db.models import ChannelListing, Product, Channel, ListingStatus
from src.schemas.channel_listing import (
    ChannelListingCreate,
    ChannelListingUpdate,
    ChannelListingRead,
)
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter()


@router.post("/", response_model=ChannelListingRead, status_code=status.HTTP_201_CREATED)
async def create_channel_listing(
    data: ChannelListingCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new channel listing."""
    # Verify product exists and belongs to tenant
    result = await session.execute(
        select(Product).where(
            Product.id == data.product_id,
            Product.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Product not found",
        )

    # Check for duplicate channel + channelSku
    result = await session.execute(
        select(ChannelListing).where(
            ChannelListing.channel == data.channel,
            ChannelListing.channel_sku == data.channel_sku,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Listing with this channel and SKU already exists",
        )

    listing = ChannelListing(
        tenant_id=current_user.tenant_id,
        **data.model_dump(by_alias=False, exclude_none=True),
    )
    session.add(listing)
    await session.commit()
    await session.refresh(listing)
    return listing


@router.get("/", response_model=PaginatedResponse[ChannelListingRead])
async def list_channel_listings(
    session: DbSession,
    current_user: CurrentUser,
    channel: Channel | None = None,
    status: ListingStatus | None = Query(None),
    product_id: UUID | None = Query(None, alias="productId"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List channel listings with pagination."""
    query = select(ChannelListing).where(ChannelListing.tenant_id == current_user.tenant_id)

    if channel:
        query = query.where(ChannelListing.channel == channel)
    if status:
        query = query.where(ChannelListing.status == status)
    if product_id:
        query = query.where(ChannelListing.product_id == product_id)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(ChannelListing.updated_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    listings = result.scalars().all()

    return PaginatedResponse(
        data=[ChannelListingRead.model_validate(l) for l in listings],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/by-product/{product_id}", response_model=list[ChannelListingRead])
async def list_listings_by_product(
    product_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """List all channel listings for a product."""
    result = await session.execute(
        select(ChannelListing)
        .where(
            ChannelListing.product_id == product_id,
            ChannelListing.tenant_id == current_user.tenant_id,
        )
        .order_by(ChannelListing.channel)
    )
    return result.scalars().all()


@router.get("/{listing_id}", response_model=ChannelListingRead)
async def get_channel_listing(
    listing_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single channel listing."""
    result = await session.execute(
        select(ChannelListing).where(
            ChannelListing.id == listing_id,
            ChannelListing.tenant_id == current_user.tenant_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel listing not found",
        )
    return listing


@router.patch("/{listing_id}", response_model=ChannelListingRead)
async def update_channel_listing(
    listing_id: UUID,
    data: ChannelListingUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a channel listing."""
    result = await session.execute(
        select(ChannelListing).where(
            ChannelListing.id == listing_id,
            ChannelListing.tenant_id == current_user.tenant_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel listing not found",
        )

    # Check for duplicate channel_sku if changing
    if data.channel_sku and data.channel_sku != listing.channel_sku:
        result = await session.execute(
            select(ChannelListing).where(
                ChannelListing.channel == listing.channel,
                ChannelListing.channel_sku == data.channel_sku,
                ChannelListing.id != listing_id,
            )
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Listing with this channel and SKU already exists",
            )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(listing, field, value)

    await session.commit()
    await session.refresh(listing)
    return listing


@router.delete("/{listing_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_channel_listing(
    listing_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a channel listing."""
    result = await session.execute(
        select(ChannelListing).where(
            ChannelListing.id == listing_id,
            ChannelListing.tenant_id == current_user.tenant_id,
        )
    )
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel listing not found",
        )

    await session.delete(listing)
    await session.commit()
