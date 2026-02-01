"""Inventory factories: Location, StockItem, StockMovement."""

from datetime import datetime, timedelta
from decimal import Decimal
import random

import factory
from faker import Faker

from src.db.models.inventory import Location, StockItem, StockMovement
from src.db.models.enums import LocationType, MovementType, Channel
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# Realistic warehouse location data
WAREHOUSE_NAMES = [
    "Main Warehouse", "West Coast DC", "East Coast DC", "Central Hub",
    "Overflow Storage", "Returns Center", "Quality Hold", "FBA Prep Center"
]

FBA_NAMES = [
    "FBA - PHX3", "FBA - ONT8", "FBA - SBD1", "FBA - LGB8",
    "FBA - SMF3", "FBA - TEB4", "FBA - MDW2", "FBA - AVP1"
]


class LocationFactory(AsyncSQLAlchemyFactory):
    """Factory for Location model."""

    class Meta:
        model = Location

    tenant_id = None
    name = factory.LazyFunction(lambda: random.choice(WAREHOUSE_NAMES))
    type = LocationType.WAREHOUSE
    channel = None
    address = factory.LazyFunction(lambda: {
        "street": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "postal_code": fake.zipcode(),
        "country": "US",
    })
    is_active = True

    class Params:
        fba = factory.Trait(
            name=factory.LazyFunction(lambda: random.choice(FBA_NAMES)),
            type=LocationType.FBA,
            channel=Channel.AMAZON,
        )
        store = factory.Trait(
            name=factory.LazyFunction(lambda: f"Store #{random.randint(100, 999)}"),
            type=LocationType.STORE,
        )


class StockItemFactory(AsyncSQLAlchemyFactory):
    """Factory for StockItem model."""

    class Meta:
        model = StockItem

    tenant_id = None
    product_id = None
    location_id = None

    quantity_available = factory.LazyFunction(lambda: random.randint(0, 500))
    quantity_reserved = factory.LazyFunction(lambda: random.randint(0, 20))
    quantity_inbound = factory.LazyFunction(lambda: random.choice([0, 0, 0, random.randint(10, 100)]))

    reorder_point = factory.LazyFunction(lambda: random.choice([10, 25, 50, 100]))
    reorder_qty = factory.LazyAttribute(lambda o: o.reorder_point * 2)

    cost_basis = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(5, 100), 2))))
    bin_location = factory.LazyFunction(lambda: f"{random.choice('ABCDEF')}-{random.randint(1, 50)}-{random.randint(1, 4)}")

    class Params:
        low_stock = factory.Trait(
            quantity_available=factory.LazyFunction(lambda: random.randint(1, 10)),
            quantity_reserved=0,
        )
        out_of_stock = factory.Trait(
            quantity_available=0,
            quantity_reserved=0,
            quantity_inbound=factory.LazyFunction(lambda: random.randint(50, 200)),
        )


class StockMovementFactory(AsyncSQLAlchemyFactory):
    """Factory for StockMovement model."""

    class Meta:
        model = StockMovement

    tenant_id = None
    stock_item_id = None

    type = factory.LazyFunction(lambda: random.choice([
        MovementType.RECEIVE, MovementType.SHIP, MovementType.ADJUST
    ]))
    quantity = factory.LazyAttribute(
        lambda o: random.randint(1, 50) if o.type != MovementType.ADJUST else random.randint(-10, 10)
    )
    reference = factory.LazyAttribute(
        lambda o: {
            MovementType.RECEIVE: f"PO-{random.randint(10000, 99999)}",
            MovementType.SHIP: f"ORD-{random.randint(100000, 999999)}",
            MovementType.ADJUST: f"ADJ-{random.randint(1000, 9999)}",
            MovementType.TRANSFER: f"TRF-{random.randint(1000, 9999)}",
            MovementType.DAMAGE: f"DMG-{random.randint(1000, 9999)}",
            MovementType.COUNT: f"CNT-{random.randint(1000, 9999)}",
        }.get(o.type, None)
    )
    notes = factory.LazyFunction(lambda: random.choice([None, fake.sentence()]))
    created_by = factory.LazyFunction(lambda: fake.email())
    created_at = factory.LazyFunction(
        lambda: datetime.utcnow() - timedelta(days=random.randint(0, 90))
    )
