"""Factory definitions for test data generation."""

from src.factories.base import AsyncSQLAlchemyFactory, get_session_context
from src.factories.tenant import TenantFactory
from src.factories.user import UserFactory
from src.factories.product import (
    ProductFactory,
    ProductImageFactory,
    ProductAttributeFactory,
    VariationProductFactory,
)
from src.factories.category import CategoryFactory
from src.factories.vendor import (
    VendorFactory,
    VendorContactFactory,
    VendorAddressFactory,
    VendorProductFactory,
)
from src.factories.inventory import (
    LocationFactory,
    StockItemFactory,
    StockMovementFactory,
)
from src.factories.purchase_order import (
    PurchaseOrderFactory,
    POLineFactory,
)

__all__ = [
    # Base
    "AsyncSQLAlchemyFactory",
    "get_session_context",
    # Tenant/User
    "TenantFactory",
    "UserFactory",
    # Product
    "ProductFactory",
    "ProductImageFactory",
    "ProductAttributeFactory",
    "VariationProductFactory",
    # Category
    "CategoryFactory",
    # Vendor
    "VendorFactory",
    "VendorContactFactory",
    "VendorAddressFactory",
    "VendorProductFactory",
    # Inventory
    "LocationFactory",
    "StockItemFactory",
    "StockMovementFactory",
    # Purchase Orders
    "PurchaseOrderFactory",
    "POLineFactory",
]
