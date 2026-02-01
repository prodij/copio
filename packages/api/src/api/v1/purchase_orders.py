"""Purchase orders API endpoints."""

from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import selectinload

from src.api.deps import DbSession, CurrentUser
from src.auth.dependencies import require_permission
from src.db.models import (
    PurchaseOrder,
    POLine,
    Vendor,
    Location,
    Product,
    VendorProduct,
    StockItem,
    StockMovement,
    POStatus,
    ShipmentStatus,
    MovementType,
)
from src.schemas.purchase_order import (
    PurchaseOrderCreate,
    PurchaseOrderUpdate,
    PurchaseOrderRead,
    PurchaseOrderListItem,
    POLineCreate,
    POLineUpdate,
    POLineRead,
    ReceiveItemsRequest,
    TrackingUpdate,
    FollowUpUpdate,
    LogContactRequest,
    CreateFromVendorRequest,
)

router = APIRouter()


# =============================================================================
# HELPERS
# =============================================================================

async def generate_po_number(session, tenant_id: UUID) -> str:
    """Generate a unique PO number."""
    year = datetime.now().year
    prefix = f"PO-{year}-"
    
    result = await session.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.tenant_id == tenant_id,
            PurchaseOrder.po_number.startswith(prefix),
        )
        .order_by(PurchaseOrder.po_number.desc())
        .limit(1)
    )
    last_po = result.scalar_one_or_none()
    
    sequence = 1
    if last_po:
        try:
            last_seq = int(last_po.po_number.replace(prefix, ""))
            sequence = last_seq + 1
        except ValueError:
            pass
    
    return f"{prefix}{str(sequence).zfill(4)}"


def calculate_totals(lines: list) -> dict:
    """Calculate PO totals from lines."""
    subtotal = sum(line.quantity_ordered * float(line.unit_cost) for line in lines)
    return {"subtotal": Decimal(subtotal), "total": Decimal(subtotal)}


# =============================================================================
# PURCHASE ORDER CRUD
# =============================================================================

@router.get("/", response_model=dict)
async def list_purchase_orders(
    session: DbSession,
    current_user: CurrentUser,
    status: POStatus | None = Query(None),
    vendor_id: UUID | None = Query(None, alias="vendorId"),
    destination_id: UUID | None = Query(None, alias="destinationId"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List purchase orders."""
    query = select(PurchaseOrder).where(PurchaseOrder.tenant_id == current_user.tenant_id)

    if status:
        query = query.where(PurchaseOrder.status == status)
    if vendor_id:
        query = query.where(PurchaseOrder.vendor_id == vendor_id)
    if destination_id:
        query = query.where(PurchaseOrder.destination_id == destination_id)

    # Get total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await session.execute(count_query)).scalar_one()

    # Get POs with relationships
    query = (
        query
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines),
        )
        .order_by(PurchaseOrder.created_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await session.execute(query)
    purchase_orders = result.scalars().all()

    return {
        "purchaseOrders": [PurchaseOrderRead.model_validate(po) for po in purchase_orders],
        "total": total,
    }


@router.get("/follow-ups/due", response_model=list[PurchaseOrderRead])
async def get_follow_ups_due(
    session: DbSession,
    current_user: CurrentUser,
):
    """Get POs needing follow-up."""
    now = datetime.now()
    three_days_ago = now - timedelta(days=3)
    two_days_ago = now - timedelta(days=2)

    result = await session.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.tenant_id == current_user.tenant_id,
            PurchaseOrder.status.in_([POStatus.SUBMITTED, POStatus.CONFIRMED, POStatus.SHIPPED]),
            or_(
                PurchaseOrder.next_follow_up_at <= now,
                and_(
                    PurchaseOrder.next_follow_up_at.is_(None),
                    PurchaseOrder.last_contacted_at < three_days_ago,
                ),
                and_(
                    PurchaseOrder.next_follow_up_at.is_(None),
                    PurchaseOrder.last_contacted_at.is_(None),
                    PurchaseOrder.ordered_at < two_days_ago,
                ),
            ),
        )
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
        )
        .order_by(PurchaseOrder.next_follow_up_at.asc(), PurchaseOrder.ordered_at.asc())
    )
    return result.scalars().all()


@router.get("/shipments/in-transit", response_model=list[PurchaseOrderRead])
async def get_shipments_in_transit(
    session: DbSession,
    current_user: CurrentUser,
):
    """Get POs with shipments in transit."""
    result = await session.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.tenant_id == current_user.tenant_id,
            PurchaseOrder.status == POStatus.SHIPPED,
            PurchaseOrder.shipment_status.in_([
                ShipmentStatus.LABEL_CREATED,
                ShipmentStatus.IN_TRANSIT,
                ShipmentStatus.OUT_FOR_DELIVERY,
            ]),
        )
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
        )
        .order_by(PurchaseOrder.expected_at.asc())
    )
    return result.scalars().all()


@router.get("/{po_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(
    po_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Get a single purchase order."""
    result = await session.execute(
        select(PurchaseOrder)
        .where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
        .options(
            selectinload(PurchaseOrder.vendor).selectinload(Vendor.contacts),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines).selectinload(POLine.product),
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )
    return po


@router.post("/", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a new purchase order."""
    # Verify vendor
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == data.vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vendor not found",
        )

    # Verify destination
    result = await session.execute(
        select(Location).where(
            Location.id == data.destination_id,
            Location.tenant_id == current_user.tenant_id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Destination location not found",
        )

    po_number = await generate_po_number(session, current_user.tenant_id)
    expected_at = datetime.now() + timedelta(days=vendor.lead_time_days)

    # Process lines
    line_data = []
    if data.lines:
        for line in data.lines:
            # Get unit cost from vendor product if not provided
            unit_cost = line.unit_cost
            if unit_cost is None:
                vp_result = await session.execute(
                    select(VendorProduct).where(
                        VendorProduct.vendor_id == data.vendor_id,
                        VendorProduct.product_id == line.product_id,
                    )
                )
                vp = vp_result.scalar_one_or_none()
                unit_cost = vp.unit_cost if vp else Decimal(0)

            line_data.append({
                "product_id": line.product_id,
                "quantity_ordered": line.quantity_ordered,
                "unit_cost": unit_cost,
                "notes": line.notes,
            })

    # Calculate totals
    subtotal = sum(l["quantity_ordered"] * float(l["unit_cost"]) for l in line_data)
    total = subtotal

    po = PurchaseOrder(
        tenant_id=current_user.tenant_id,
        po_number=po_number,
        vendor_id=data.vendor_id,
        destination_id=data.destination_id,
        notes=data.notes,
        expected_at=expected_at,
        subtotal=Decimal(subtotal),
        total=Decimal(total),
    )
    session.add(po)
    await session.flush()

    # Add lines
    for ld in line_data:
        line = POLine(po_id=po.id, **ld)
        session.add(line)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines).selectinload(POLine.product),
        )
        .where(PurchaseOrder.id == po.id)
    )
    return result.scalar_one()


@router.patch("/{po_id}", response_model=PurchaseOrderRead)
async def update_purchase_order(
    po_id: UUID,
    data: PurchaseOrderUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a purchase order."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status in [POStatus.RECEIVED, POStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify a completed or cancelled PO",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)

    # Recalculate total if tax/shipping changed
    if "tax" in update_data or "shipping" in update_data:
        subtotal = float(po.subtotal or 0)
        tax = float(update_data.get("tax", po.tax or 0))
        shipping = float(update_data.get("shipping", po.shipping or 0))
        update_data["total"] = Decimal(subtotal + tax + shipping)

    # Set ordered_at when submitting
    if update_data.get("status") == POStatus.SUBMITTED and not po.ordered_at:
        update_data["ordered_at"] = datetime.now()

    for field, value in update_data.items():
        setattr(po, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines),
        )
        .where(PurchaseOrder.id == po_id)
    )
    return result.scalar_one()


@router.delete("/{po_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_purchase_order(
    po_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a purchase order."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status not in [POStatus.DRAFT, POStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete draft or cancelled POs",
        )

    await session.delete(po)
    await session.commit()


# =============================================================================
# PO LINES
# =============================================================================

@router.post("/{po_id}/lines", response_model=POLineRead, status_code=status.HTTP_201_CREATED)
async def add_po_line(
    po_id: UUID,
    data: POLineCreate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Add a line to a purchase order."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status != POStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only add lines to draft POs",
        )

    # Check for existing line with same product
    result = await session.execute(
        select(POLine).where(
            POLine.po_id == po_id,
            POLine.product_id == data.product_id,
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Line for this product already exists. Update it instead.",
        )

    # Get unit cost from vendor product if not provided
    unit_cost = data.unit_cost
    if unit_cost is None:
        vp_result = await session.execute(
            select(VendorProduct).where(
                VendorProduct.vendor_id == po.vendor_id,
                VendorProduct.product_id == data.product_id,
            )
        )
        vp = vp_result.scalar_one_or_none()
        unit_cost = vp.unit_cost if vp else Decimal(0)

    line = POLine(
        po_id=po_id,
        product_id=data.product_id,
        quantity_ordered=data.quantity_ordered,
        unit_cost=unit_cost,
        notes=data.notes,
    )
    session.add(line)
    await session.flush()

    # Recalculate totals
    result = await session.execute(
        select(POLine).where(POLine.po_id == po_id)
    )
    all_lines = result.scalars().all()
    totals = calculate_totals(all_lines)
    po.subtotal = totals["subtotal"]
    po.total = totals["total"] + Decimal(po.tax or 0) + Decimal(po.shipping or 0)

    await session.commit()

    # Reload with product
    result = await session.execute(
        select(POLine)
        .options(selectinload(POLine.product))
        .where(POLine.id == line.id)
    )
    return result.scalar_one()


@router.patch("/{po_id}/lines/{line_id}", response_model=POLineRead)
async def update_po_line(
    po_id: UUID,
    line_id: UUID,
    data: POLineUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update a PO line."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status not in [POStatus.DRAFT, POStatus.SUBMITTED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only modify lines on draft or submitted POs",
        )

    result = await session.execute(
        select(POLine).where(
            POLine.id == line_id,
            POLine.po_id == po_id,
        )
    )
    line = result.scalar_one_or_none()
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(line, field, value)

    # Recalculate totals
    result = await session.execute(
        select(POLine).where(POLine.po_id == po_id)
    )
    all_lines = result.scalars().all()
    totals = calculate_totals(all_lines)
    po.subtotal = totals["subtotal"]
    po.total = totals["total"] + Decimal(po.tax or 0) + Decimal(po.shipping or 0)

    await session.commit()

    # Reload with product
    result = await session.execute(
        select(POLine)
        .options(selectinload(POLine.product))
        .where(POLine.id == line_id)
    )
    return result.scalar_one()


@router.delete("/{po_id}/lines/{line_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_po_line(
    po_id: UUID,
    line_id: UUID,
    session: DbSession,
    current_user: CurrentUser,
):
    """Delete a PO line."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status != POStatus.DRAFT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only delete lines from draft POs",
        )

    result = await session.execute(
        select(POLine).where(
            POLine.id == line_id,
            POLine.po_id == po_id,
        )
    )
    line = result.scalar_one_or_none()
    if not line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Line not found",
        )

    await session.delete(line)

    # Recalculate totals
    result = await session.execute(
        select(POLine).where(POLine.po_id == po_id)
    )
    all_lines = result.scalars().all()
    totals = calculate_totals(all_lines)
    po.subtotal = totals["subtotal"]
    po.total = totals["total"] + Decimal(po.tax or 0) + Decimal(po.shipping or 0)

    await session.commit()


# =============================================================================
# RECEIVING
# =============================================================================

@router.post("/{po_id}/receive", response_model=PurchaseOrderRead)
async def receive_items(
    po_id: UUID,
    data: ReceiveItemsRequest,
    session: DbSession,
    current_user: CurrentUser,
):
    """Receive items against a PO."""
    result = await session.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    if po.status in [POStatus.RECEIVED, POStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot receive items on a completed or cancelled PO",
        )

    # Process each line
    for receive_line in data.lines:
        line = next((l for l in po.lines if l.id == receive_line.line_id), None)
        if not line:
            continue

        new_received = line.quantity_received + receive_line.quantity_received
        line.quantity_received = new_received

        # Update or create stock item
        result = await session.execute(
            select(StockItem).where(
                StockItem.product_id == line.product_id,
                StockItem.location_id == po.destination_id,
            )
        )
        stock_item = result.scalar_one_or_none()

        if stock_item:
            stock_item.quantity_available += receive_line.quantity_received
            stock_item.quantity_inbound = max(0, stock_item.quantity_inbound - receive_line.quantity_received)
        else:
            stock_item = StockItem(
                tenant_id=current_user.tenant_id,
                product_id=line.product_id,
                location_id=po.destination_id,
                quantity_available=receive_line.quantity_received,
                cost_basis=line.unit_cost,
            )
            session.add(stock_item)
            await session.flush()

        # Create movement record
        movement = StockMovement(
            tenant_id=current_user.tenant_id,
            stock_item_id=stock_item.id,
            type=MovementType.RECEIVE,
            quantity=receive_line.quantity_received,
            reference=po.po_number,
            notes=f"Received from PO {po.po_number}",
            created_by=str(current_user.id),
        )
        session.add(movement)

    # Check if all lines are fully received
    await session.flush()
    result = await session.execute(
        select(POLine).where(POLine.po_id == po_id)
    )
    updated_lines = result.scalars().all()
    all_received = all(l.quantity_received >= l.quantity_ordered for l in updated_lines)
    some_received = any(l.quantity_received > 0 for l in updated_lines)

    if all_received:
        po.status = POStatus.RECEIVED
        po.received_at = datetime.now()
    elif some_received and po.status != POStatus.PARTIAL:
        po.status = POStatus.PARTIAL

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines).selectinload(POLine.product),
        )
        .where(PurchaseOrder.id == po_id)
    )
    return result.scalar_one()


# =============================================================================
# TRACKING & FOLLOW-UP
# =============================================================================

@router.patch("/{po_id}/tracking", response_model=PurchaseOrderRead)
async def update_tracking(
    po_id: UUID,
    data: TrackingUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update tracking information."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)

    # Auto-generate tracking URL
    if data.tracking_number and not data.tracking_url and data.carrier:
        carrier_urls = {
            "UPS": f"https://www.ups.com/track?tracknum={data.tracking_number}",
            "FEDEX": f"https://www.fedex.com/fedextrack/?trknbr={data.tracking_number}",
            "USPS": f"https://tools.usps.com/go/TrackConfirmAction?tLabels={data.tracking_number}",
            "DHL": f"https://www.dhl.com/en/express/tracking.html?AWB={data.tracking_number}",
        }
        update_data["tracking_url"] = carrier_urls.get(data.carrier.upper())

    # Auto-set status to SHIPPED
    if data.tracking_number and po.status not in [POStatus.SHIPPED, POStatus.PARTIAL, POStatus.RECEIVED, POStatus.CANCELLED]:
        update_data["status"] = POStatus.SHIPPED

    # Set shipped_at if not already set
    if data.tracking_number and not po.shipped_at:
        update_data["shipped_at"] = datetime.now()

    update_data["last_tracking_update"] = datetime.now()

    for field, value in update_data.items():
        setattr(po, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
        )
        .where(PurchaseOrder.id == po_id)
    )
    return result.scalar_one()


@router.patch("/{po_id}/follow-up", response_model=PurchaseOrderRead)
async def update_follow_up(
    po_id: UUID,
    data: FollowUpUpdate,
    session: DbSession,
    current_user: CurrentUser,
):
    """Update follow-up information."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    update_data = data.model_dump(by_alias=False, exclude_none=True)
    for field, value in update_data.items():
        setattr(po, field, value)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
        )
        .where(PurchaseOrder.id == po_id)
    )
    return result.scalar_one()


@router.post("/{po_id}/log-contact", response_model=PurchaseOrderRead)
async def log_vendor_contact(
    po_id: UUID,
    data: LogContactRequest,
    session: DbSession,
    current_user: CurrentUser,
):
    """Log a vendor contact."""
    result = await session.execute(
        select(PurchaseOrder).where(
            PurchaseOrder.id == po_id,
            PurchaseOrder.tenant_id == current_user.tenant_id,
        )
    )
    po = result.scalar_one_or_none()
    if not po:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Purchase order not found",
        )

    po.last_contacted_at = datetime.now()

    if data.next_follow_up_days:
        po.next_follow_up_at = datetime.now() + timedelta(days=data.next_follow_up_days)
    else:
        po.next_follow_up_at = None

    if data.notes:
        po.follow_up_notes = data.notes

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
        )
        .where(PurchaseOrder.id == po_id)
    )
    return result.scalar_one()


# =============================================================================
# CREATE FROM VENDOR
# =============================================================================

@router.post("/from-vendor/{vendor_id}", response_model=PurchaseOrderRead, status_code=status.HTTP_201_CREATED)
async def create_from_vendor(
    vendor_id: UUID,
    data: CreateFromVendorRequest,
    session: DbSession,
    current_user: CurrentUser,
):
    """Create a PO from vendor products."""
    # Verify vendor
    result = await session.execute(
        select(Vendor).where(
            Vendor.id == vendor_id,
            Vendor.tenant_id == current_user.tenant_id,
        )
    )
    vendor = result.scalar_one_or_none()
    if not vendor:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vendor not found",
        )

    # Get vendor products
    query = select(VendorProduct).where(
        VendorProduct.vendor_id == vendor_id,
        VendorProduct.is_active == True,
    )
    if data.product_ids:
        query = query.where(VendorProduct.product_id.in_(data.product_ids))

    result = await session.execute(query.options(selectinload(VendorProduct.product)))
    vendor_products = result.scalars().all()

    if not vendor_products:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active products found for this vendor",
        )

    po_number = await generate_po_number(session, current_user.tenant_id)
    expected_at = datetime.now() + timedelta(days=vendor.lead_time_days)

    # Create lines with MOQ as default quantity
    line_data = [
        {
            "product_id": vp.product_id,
            "quantity_ordered": vp.min_order_qty,
            "unit_cost": vp.unit_cost,
        }
        for vp in vendor_products
    ]

    subtotal = sum(l["quantity_ordered"] * float(l["unit_cost"]) for l in line_data)

    po = PurchaseOrder(
        tenant_id=current_user.tenant_id,
        po_number=po_number,
        vendor_id=vendor_id,
        destination_id=data.destination_id,
        notes=data.notes,
        expected_at=expected_at,
        subtotal=Decimal(subtotal),
        total=Decimal(subtotal),
    )
    session.add(po)
    await session.flush()

    for ld in line_data:
        line = POLine(po_id=po.id, **ld)
        session.add(line)

    await session.commit()

    # Reload with relationships
    result = await session.execute(
        select(PurchaseOrder)
        .options(
            selectinload(PurchaseOrder.vendor),
            selectinload(PurchaseOrder.destination),
            selectinload(PurchaseOrder.lines).selectinload(POLine.product),
        )
        .where(PurchaseOrder.id == po.id)
    )
    return result.scalar_one()
