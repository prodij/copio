"""Purchase order factories."""

from datetime import datetime, timedelta
from decimal import Decimal
import random

import factory
from faker import Faker

from src.db.models.purchase_order import PurchaseOrder, POLine
from src.db.models.enums import POStatus, ShipmentStatus
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# PO number counter for sequential generation
_po_counter = random.randint(10000, 20000)


def generate_po_number() -> str:
    """Generate a sequential PO number."""
    global _po_counter
    _po_counter += 1
    return f"PO-{_po_counter}"


CARRIERS = ["UPS", "FedEx", "USPS", "DHL", "Amazon Logistics", "OnTrac", "LaserShip"]


class PurchaseOrderFactory(AsyncSQLAlchemyFactory):
    """Factory for PurchaseOrder model."""

    class Meta:
        model = PurchaseOrder

    tenant_id = None
    po_number = factory.LazyFunction(generate_po_number)
    vendor_id = None
    destination_id = None

    status = factory.LazyFunction(lambda: random.choice([
        POStatus.DRAFT, POStatus.SUBMITTED, POStatus.CONFIRMED,
        POStatus.SHIPPED, POStatus.RECEIVED
    ]))

    notes = factory.LazyFunction(lambda: random.choice([None, fake.sentence()]))

    # Financials (will be calculated based on lines in reality)
    subtotal = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(500, 10000), 2))))
    tax = factory.LazyAttribute(lambda o: o.subtotal * Decimal("0.0825"))
    shipping = factory.LazyFunction(lambda: Decimal(str(random.choice([0, 25, 50, 100, 250]))))
    total = factory.LazyAttribute(lambda o: o.subtotal + o.tax + o.shipping)

    # Dates
    ordered_at = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(days=random.randint(1, 60))
    )
    expected_at = factory.LazyAttribute(
        lambda o: o.ordered_at + timedelta(days=random.randint(7, 30)) if o.ordered_at else None
    )
    shipped_at = factory.LazyAttribute(
        lambda o: o.ordered_at + timedelta(days=random.randint(1, 5)) 
        if o.status in [POStatus.SHIPPED, POStatus.RECEIVED] else None
    )
    received_at = factory.LazyAttribute(
        lambda o: o.shipped_at + timedelta(days=random.randint(3, 10)) 
        if o.status == POStatus.RECEIVED and o.shipped_at else None
    )

    # Shipping/Tracking
    carrier = factory.LazyAttribute(
        lambda o: random.choice(CARRIERS) if o.status in [POStatus.SHIPPED, POStatus.RECEIVED] else None
    )
    tracking_number = factory.LazyAttribute(
        lambda o: f"1Z{random.randint(100000000, 999999999)}" if o.carrier else None
    )
    shipment_status = factory.LazyAttribute(
        lambda o: (
            ShipmentStatus.DELIVERED if o.status == POStatus.RECEIVED
            else ShipmentStatus.IN_TRANSIT if o.status == POStatus.SHIPPED
            else None
        )
    )

    # Vendor reference
    vendor_order_number = factory.LazyFunction(
        lambda: f"VO-{random.randint(100000, 999999)}" if random.random() > 0.3 else None
    )

    class Params:
        draft = factory.Trait(
            status=POStatus.DRAFT,
            ordered_at=None,
            expected_at=None,
            carrier=None,
            tracking_number=None,
        )
        shipped = factory.Trait(
            status=POStatus.SHIPPED,
            shipment_status=ShipmentStatus.IN_TRANSIT,
        )
        received = factory.Trait(
            status=POStatus.RECEIVED,
            shipment_status=ShipmentStatus.DELIVERED,
        )


class POLineFactory(AsyncSQLAlchemyFactory):
    """Factory for POLine model."""

    class Meta:
        model = POLine

    po_id = None
    product_id = None

    quantity_ordered = factory.LazyFunction(lambda: random.choice([6, 12, 24, 48, 96, 144]))
    quantity_received = factory.LazyAttribute(
        lambda o: o.quantity_ordered if random.random() > 0.2 else random.randint(0, o.quantity_ordered)
    )

    unit_cost = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(5, 100), 2))))

    notes = factory.LazyFunction(lambda: random.choice([None, None, None, fake.sentence()]))
