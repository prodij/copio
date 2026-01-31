"""Enum definitions matching Prisma schema."""

import enum


class ProductType(str, enum.Enum):
    SIMPLE = "SIMPLE"
    PARENT = "PARENT"
    VARIATION = "VARIATION"


class ProductStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class Channel(str, enum.Enum):
    AMAZON = "AMAZON"
    SHOPIFY = "SHOPIFY"
    WALMART = "WALMART"
    EBAY = "EBAY"


class ListingStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUPPRESSED = "SUPPRESSED"
    ERROR = "ERROR"


class FulfillmentChannel(str, enum.Enum):
    MERCHANT = "MERCHANT"
    MARKETPLACE = "MARKETPLACE"
    DROPSHIP = "DROPSHIP"
    THREEPEL = "THREEPEL"


class LocationType(str, enum.Enum):
    WAREHOUSE = "WAREHOUSE"
    FBA = "FBA"
    THREEPEL = "THREEPEL"
    STORE = "STORE"


class MovementType(str, enum.Enum):
    RECEIVE = "RECEIVE"
    SHIP = "SHIP"
    ADJUST = "ADJUST"
    TRANSFER = "TRANSFER"
    DAMAGE = "DAMAGE"
    COUNT = "COUNT"


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    ALLOCATED = "ALLOCATED"
    PICKING = "PICKING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class VendorTier(str, enum.Enum):
    STRATEGIC = "STRATEGIC"
    PREFERRED = "PREFERRED"
    STANDARD = "STANDARD"
    PROBATION = "PROBATION"
    SUSPENDED = "SUSPENDED"


class ContactRole(str, enum.Enum):
    GENERAL = "GENERAL"
    SALES = "SALES"
    ACCOUNT = "ACCOUNT"
    SUPPORT = "SUPPORT"
    BILLING = "BILLING"
    SHIPPING = "SHIPPING"
    EXECUTIVE = "EXECUTIVE"


class AddressType(str, enum.Enum):
    CORPORATE = "CORPORATE"
    BILLING = "BILLING"
    WAREHOUSE = "WAREHOUSE"
    RETURNS = "RETURNS"
    OTHER = "OTHER"


class DocumentType(str, enum.Enum):
    W9 = "W9"
    W8 = "W8"
    COI = "COI"
    CONTRACT = "CONTRACT"
    PRICE_LIST = "PRICE_LIST"
    CATALOG = "CATALOG"
    SPEC_SHEET = "SPEC_SHEET"
    CERTIFICATE = "CERTIFICATE"
    LICENSE = "LICENSE"
    IMPORT_PERMIT = "IMPORT_PERMIT"
    OTHER = "OTHER"


class POStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    SHIPPED = "SHIPPED"
    PARTIAL = "PARTIAL"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class ShipmentStatus(str, enum.Enum):
    PENDING = "PENDING"
    LABEL_CREATED = "LABEL_CREATED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    EXCEPTION = "EXCEPTION"
