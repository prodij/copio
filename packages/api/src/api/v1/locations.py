"""Locations API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from src.api.deps import DbSession, CurrentUser
from src.db.models import Location, LocationType
from src.schemas.common import PaginatedResponse, Pagination
from src.schemas.inventory import (
    LocationCreate,
    LocationUpdate,
    LocationRead,
)

router = APIRouter()


@router.post("/", response_model=LocationRead, status_code=status.HTTP_201_CREATED)
async def create_location(
    data: LocationCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new location."""
    location = Location(
        tenant_id=current_user.tenant_id,
        **data.model_dump(by_alias=False),
    )
    session.add(location)
    await session.commit()
    await session.refresh(location)
    return location


@router.get("/", response_model=PaginatedResponse[LocationRead])
async def list_locations(
    session: DbSession,
    current_user: CurrentUser,
    type: LocationType | None = None,
    active: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100, alias="pageSize"),
):
    """List all locations for the tenant."""
    query = select(Location).where(Location.tenant_id == current_user.tenant_id)

    if type:
        query = query.where(Location.type == type)
    if active is not None:
        query = query.where(Location.is_active == active)

    # Count total
    count_result = await session.execute(
        select(func.count()).select_from(query.subquery())
    )
    total = count_result.scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(Location.name).offset(offset).limit(page_size)
    result = await session.execute(query)
    locations = result.scalars().all()

    return PaginatedResponse(
        data=[LocationRead.model_validate(loc) for loc in locations],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/{location_id}", response_model=LocationRead)
async def get_location(
    location_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single location."""
    result = await session.execute(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == current_user.tenant_id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )
    return location


@router.patch("/{location_id}", response_model=LocationRead)
async def update_location(
    location_id: UUID,
    data: LocationUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a location."""
    result = await session.execute(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == current_user.tenant_id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(location, field, value)

    await session.commit()
    await session.refresh(location)
    return location


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_location(
    location_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a location."""
    result = await session.execute(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == current_user.tenant_id,
        )
    )
    location = result.scalar_one_or_none()
    if not location:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Location not found",
        )

    await session.delete(location)
    await session.commit()
