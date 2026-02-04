"""Database models package."""

from src.db.models.enums import (
    ProductType,
    ProductStatus,
    Channel,
    ListingStatus,
    FulfillmentChannel,
    LocationType,
    MovementType,
    OrderStatus,
    VendorTier,
    ContactRole,
    AddressType,
    DocumentType,
    POStatus,
    ShipmentStatus,
)
from src.db.models.tenant import Tenant
from src.db.models.user import User
from src.db.models.role import Role
from src.db.models.user_role import UserRole
from src.db.models.product import Product, ProductImage, ProductAttribute
from src.db.models.category import Category, ProductCategory
from src.db.models.channel_listing import ChannelListing
from src.db.models.inventory import Location, StockItem, StockMovement
from src.db.models.order import Order, OrderLine
from src.db.models.vendor import (
    Vendor,
    VendorContact,
    VendorAddress,
    VendorDocument,
    VendorProduct,
)
from src.db.models.purchase_order import PurchaseOrder, POLine
from src.db.models.user_invite import UserInvite
from src.db.models.audit_log import AuditLog, AuditAction
from src.db.models.system_settings import SystemSettings
from src.db.models.refresh_token import RefreshToken
from src.db.models.api_key import ApiKey
from src.db.models.admin_audit_log import AdminAuditLog

__all__ = [
    # Enums
    "ProductType",
    "ProductStatus",
    "Channel",
    "ListingStatus",
    "FulfillmentChannel",
    "LocationType",
    "MovementType",
    "OrderStatus",
    "VendorTier",
    "ContactRole",
    "AddressType",
    "DocumentType",
    "POStatus",
    "ShipmentStatus",
    # Auth
    "Tenant",
    "User",
    "Role",
    "UserRole",
    # Products
    "Product",
    "ProductImage",
    "ProductAttribute",
    # Categories
    "Category",
    "ProductCategory",
    # Listings
    "ChannelListing",
    # Inventory
    "Location",
    "StockItem",
    "StockMovement",
    # Orders
    "Order",
    "OrderLine",
    # Vendors
    "Vendor",
    "VendorContact",
    "VendorAddress",
    "VendorDocument",
    "VendorProduct",
    # Purchase Orders
    "PurchaseOrder",
    "POLine",
    # User Invites
    "UserInvite",
    # Audit
    "AuditLog",
    "AuditAction",
    # System
    "SystemSettings",
    # Auth tokens
    "RefreshToken",
    "ApiKey",
    "AdminAuditLog",
]
