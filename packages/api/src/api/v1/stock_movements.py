"""Stock movements API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select, func

from src.api.deps import DbSession, CurrentUser
from src.db.models import StockMovement, StockItem, MovementType
from src.schemas.inventory import (
    StockMovementCreate,
    StockMovementRead,
)
from src.schemas.common import PaginatedResponse, Pagination

router = APIRouter()


@router.post("/", response_model=StockMovementRead, status_code=status.HTTP_201_CREATED)
async def create_stock_movement(
    data: StockMovementCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a stock movement and update stock item quantities."""
    # Verify stock item exists and belongs to tenant
    result = await session.execute(
        select(StockItem).where(
            StockItem.id == data.stock_item_id,
            StockItem.tenant_id == current_user.tenant_id,
        )
    )
    stock_item = result.scalar_one_or_none()
    if not stock_item:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock item not found",
        )

    # Update stock item quantities based on movement type
    if data.type == MovementType.RECEIVE:
        stock_item.quantity_available += data.quantity
        stock_item.quantity_inbound = max(0, stock_item.quantity_inbound - data.quantity)
    elif data.type == MovementType.SHIP:
        if stock_item.quantity_available < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient stock available",
            )
        stock_item.quantity_available -= data.quantity
    elif data.type == MovementType.ADJUST:
        stock_item.quantity_available += data.quantity  # Can be negative
    elif data.type == MovementType.DAMAGE:
        if stock_item.quantity_available < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient stock available",
            )
        stock_item.quantity_available -= data.quantity
    elif data.type == MovementType.COUNT:
        # COUNT sets the quantity directly (difference from current)
        stock_item.quantity_available = data.quantity
    elif data.type == MovementType.TRANSFER:
        # For transfer, we reduce stock here (paired with RECEIVE at destination)
        if stock_item.quantity_available < data.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Insufficient stock available",
            )
        stock_item.quantity_available -= data.quantity

    movement = StockMovement(
        tenant_id=current_user.tenant_id,
        stock_item_id=data.stock_item_id,
        type=data.type,
        quantity=data.quantity,
        reference=data.reference,
        notes=data.notes,
        created_by=str(current_user.id),
    )
    session.add(movement)
    await session.commit()
    await session.refresh(movement)
    return movement


@router.get("/", response_model=PaginatedResponse[StockMovementRead])
async def list_stock_movements(
    session: DbSession,
    current_user: CurrentUser,
    stock_item_id: UUID | None = Query(None, alias="stockItemId"),
    type: MovementType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100, alias="pageSize"),
):
    """List stock movements with pagination."""
    query = select(StockMovement).where(StockMovement.tenant_id == current_user.tenant_id)

    if stock_item_id:
        query = query.where(StockMovement.stock_item_id == stock_item_id)
    if type:
        query = query.where(StockMovement.type == type)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Apply pagination
    offset = (page - 1) * page_size
    query = query.order_by(StockMovement.created_at.desc()).offset(offset).limit(page_size)

    result = await session.execute(query)
    movements = result.scalars().all()

    return PaginatedResponse(
        data=[StockMovementRead.model_validate(m) for m in movements],
        pagination=Pagination(
            page=page,
            page_size=page_size,
            total=total,
            total_pages=(total + page_size - 1) // page_size,
        ),
    )


@router.get("/by-stock-item/{stock_item_id}", response_model=list[StockMovementRead])
async def list_movements_by_stock_item(
    stock_item_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
    limit: int = Query(50, ge=1, le=100),
):
    """List recent movements for a specific stock item."""
    result = await session.execute(
        select(StockMovement)
        .where(
            StockMovement.stock_item_id == stock_item_id,
            StockMovement.tenant_id == current_user.tenant_id,
        )
        .order_by(StockMovement.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{movement_id}", response_model=StockMovementRead)
async def get_stock_movement(
    movement_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single stock movement."""
    result = await session.execute(
        select(StockMovement).where(
            StockMovement.id == movement_id,
            StockMovement.tenant_id == current_user.tenant_id,
        )
    )
    movement = result.scalar_one_or_none()
    if not movement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stock movement not found",
        )
    return movement
