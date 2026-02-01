"""Vendor factories with realistic supplier data."""

from datetime import datetime, timedelta
from decimal import Decimal
import random

import factory
from faker import Faker

from src.db.models.vendor import Vendor, VendorContact, VendorAddress, VendorProduct
from src.db.models.enums import VendorTier, ContactRole, AddressType
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# Realistic vendor company name patterns
VENDOR_PREFIXES = ["Global", "Premier", "Direct", "Quality", "Pacific", "National", "United", "Pro"]
VENDOR_SUFFIXES = ["Supply Co", "Trading LLC", "Distributors", "Wholesale", "Industries", "Group", "Partners"]
VENDOR_SPECIALTIES = ["Electronics", "Home Goods", "Sporting Goods", "Office", "Pet", "Auto", "Garden"]


def generate_vendor_name() -> str:
    """Generate a realistic vendor company name."""
    pattern = random.choice([
        lambda: f"{fake.last_name()} {random.choice(VENDOR_SUFFIXES)}",
        lambda: f"{random.choice(VENDOR_PREFIXES)} {random.choice(VENDOR_SPECIALTIES)} {random.choice(VENDOR_SUFFIXES)}",
        lambda: f"{fake.company()}",
    ])
    return pattern()


class VendorFactory(AsyncSQLAlchemyFactory):
    """Factory for Vendor model with realistic supplier data."""

    class Meta:
        model = Vendor

    tenant_id = None
    name = factory.LazyFunction(generate_vendor_name)
    legal_name = factory.LazyAttribute(lambda o: f"{o.name} Inc.")
    code = factory.LazyFunction(lambda: f"V{random.randint(1000, 9999)}")
    tax_id = factory.LazyFunction(lambda: f"{random.randint(10, 99)}-{random.randint(1000000, 9999999)}")
    website = factory.LazyAttribute(lambda o: f"https://www.{o.name.lower().replace(' ', '').replace(',', '')[:20]}.com")

    tier = factory.LazyFunction(lambda: random.choice(list(VendorTier)))
    category = factory.LazyFunction(lambda: random.choice(VENDOR_SPECIALTIES))
    tags = factory.LazyAttribute(lambda o: [o.category.lower(), "domestic", random.choice(["reliable", "fast", "budget"])])

    # Address (legacy JSONB format)
    address = factory.LazyFunction(lambda: {
        "street": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "postal_code": fake.zipcode(),
        "country": "US",
    })
    billing_address = factory.LazyAttribute(lambda o: o.address)

    # Ordering terms
    lead_time_days = factory.LazyFunction(lambda: random.choice([7, 14, 21, 30, 45]))
    min_order_value = factory.LazyFunction(lambda: Decimal(str(random.choice([100, 250, 500, 1000, 2500]))))
    payment_terms = factory.LazyFunction(lambda: random.choice(["Net 30", "Net 45", "Net 60", "COD", "Prepaid"]))
    credit_limit = factory.LazyFunction(lambda: Decimal(str(random.choice([5000, 10000, 25000, 50000, 100000]))))
    currency = "USD"

    # Account management
    account_manager_name = factory.LazyFunction(lambda: fake.name())
    account_manager_email = factory.LazyFunction(lambda: fake.email())
    preferred_contact_method = factory.LazyFunction(lambda: random.choice(["email", "phone", "portal"]))

    # Contract dates
    contract_start_date = factory.LazyFunction(
        lambda: datetime.now() - timedelta(days=random.randint(30, 365))
    )
    contract_end_date = factory.LazyAttribute(
        lambda o: o.contract_start_date + timedelta(days=random.choice([365, 730, 1095]))
    )

    notes = factory.LazyFunction(lambda: fake.sentence())
    is_active = True

    class Params:
        strategic = factory.Trait(
            tier=VendorTier.STRATEGIC,
            credit_limit=Decimal("100000"),
            min_order_value=Decimal("100"),
        )
        probation = factory.Trait(
            tier=VendorTier.PROBATION,
            credit_limit=Decimal("5000"),
        )


class VendorContactFactory(AsyncSQLAlchemyFactory):
    """Factory for VendorContact model."""

    class Meta:
        model = VendorContact

    vendor_id = None
    name = factory.LazyFunction(lambda: fake.name())
    title = factory.LazyFunction(lambda: random.choice([
        "Sales Representative", "Account Manager", "Owner", "Purchasing Manager",
        "Customer Service", "Operations Manager", "Sales Director"
    ]))
    email = factory.LazyFunction(lambda: fake.email())
    phone = factory.LazyFunction(lambda: fake.phone_number())
    mobile = factory.LazyFunction(lambda: fake.phone_number())
    role = factory.LazyFunction(lambda: random.choice(list(ContactRole)))
    is_primary = False
    is_active = True


class VendorAddressFactory(AsyncSQLAlchemyFactory):
    """Factory for VendorAddress model."""

    class Meta:
        model = VendorAddress

    vendor_id = None
    type = AddressType.WAREHOUSE
    label = factory.LazyFunction(lambda: random.choice(["Main Warehouse", "Distribution Center", "HQ", "West Coast", "East Coast"]))
    is_primary = True

    street1 = factory.LazyFunction(lambda: fake.street_address())
    street2 = factory.LazyFunction(lambda: random.choice([None, fake.secondary_address()]))
    city = factory.LazyFunction(lambda: fake.city())
    state = factory.LazyFunction(lambda: fake.state_abbr())
    postal_code = factory.LazyFunction(lambda: fake.zipcode())
    country = "US"

    contact_name = factory.LazyFunction(lambda: fake.name())
    contact_phone = factory.LazyFunction(lambda: fake.phone_number())
    contact_email = factory.LazyFunction(lambda: fake.email())

    is_active = True


class VendorProductFactory(AsyncSQLAlchemyFactory):
    """Factory for VendorProduct (vendor-product relationship)."""

    class Meta:
        model = VendorProduct

    vendor_id = None
    product_id = None
    vendor_sku = factory.LazyFunction(lambda: f"VS-{random.randint(10000, 99999)}")
    vendor_product_name = factory.LazyFunction(lambda: fake.catch_phrase())
    
    unit_cost = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(5, 200), 4))))
    currency = "USD"

    min_order_qty = factory.LazyFunction(lambda: random.choice([1, 6, 12, 24, 48]))
    order_multiple = factory.LazyFunction(lambda: random.choice([1, 6, 12]))
    case_pack_qty = factory.LazyFunction(lambda: random.choice([None, 6, 12, 24, 48]))

    lead_time_days = factory.LazyFunction(lambda: random.choice([7, 14, 21, 30]))
    is_preferred = False
    is_active = True
