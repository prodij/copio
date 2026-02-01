"""Product factories with realistic e-commerce data."""

from decimal import Decimal
import random

import factory
from faker import Faker

from src.db.models.product import Product, ProductImage, ProductAttribute
from src.db.models.enums import ProductType, ProductStatus
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# Realistic product data pools
BRANDS = [
    "TechPro", "HomeEssentials", "GardenMaster", "FitLife", "KidZone",
    "AutoCare", "PetPals", "OfficeMax", "OutdoorGear", "BeautyBliss",
    "SoundWave", "CookMaster", "CleanPro", "SafeGuard", "ComfortZone",
]

PRODUCT_TEMPLATES = [
    # (name_template, category, weight_range, price_range)
    ("Wireless {adj} Headphones", "Electronics", (0.3, 0.8), (29.99, 299.99)),
    ("Portable {adj} Bluetooth Speaker", "Electronics", (0.5, 2.0), (19.99, 199.99)),
    ("{adj} USB-C Charging Cable 6ft", "Electronics", (0.1, 0.2), (9.99, 29.99)),
    ("{adj} Ergonomic Office Chair", "Furniture", (25, 50), (149.99, 599.99)),
    ("Adjustable Standing Desk {adj}", "Furniture", (40, 80), (299.99, 899.99)),
    ("{adj} Memory Foam Pillow", "Home", (2, 4), (29.99, 89.99)),
    ("Stainless Steel {adj} Water Bottle 32oz", "Kitchen", (0.5, 1.0), (14.99, 49.99)),
    ("{adj} Non-Stick Frying Pan Set", "Kitchen", (3, 8), (39.99, 149.99)),
    ("Resistance Bands Set {adj}", "Fitness", (0.5, 1.5), (12.99, 39.99)),
    ("{adj} Yoga Mat Premium", "Fitness", (2, 4), (19.99, 79.99)),
    ("LED {adj} Desk Lamp", "Office", (1, 3), (24.99, 89.99)),
    ("{adj} Mechanical Keyboard", "Electronics", (1, 2), (49.99, 199.99)),
    ("Wireless {adj} Mouse", "Electronics", (0.1, 0.3), (19.99, 79.99)),
    ("{adj} Garden Hose 50ft", "Garden", (3, 6), (29.99, 79.99)),
    ("Cordless {adj} Drill Set", "Tools", (3, 6), (59.99, 249.99)),
    ("{adj} Pet Bed Large", "Pets", (2, 5), (29.99, 99.99)),
    ("Automatic {adj} Pet Feeder", "Pets", (2, 4), (39.99, 129.99)),
    ("{adj} Backpack 40L", "Outdoor", (1, 2), (49.99, 149.99)),
    ("Camping {adj} Tent 4-Person", "Outdoor", (5, 10), (99.99, 399.99)),
    ("{adj} Face Moisturizer 4oz", "Beauty", (0.3, 0.5), (14.99, 59.99)),
]

ADJECTIVES = [
    "Premium", "Pro", "Elite", "Ultra", "Deluxe", "Advanced", "Smart",
    "Classic", "Modern", "Essential", "Professional", "Sport", "Compact",
]


def generate_sku() -> str:
    """Generate a realistic SKU."""
    prefix = random.choice(["CP", "INV", "SKU", "PRD"])
    number = random.randint(10000, 99999)
    suffix = random.choice(["A", "B", "C", "D", "X", "Z", ""])
    return f"{prefix}-{number}{suffix}"


def generate_upc() -> str:
    """Generate a realistic UPC."""
    return "".join([str(random.randint(0, 9)) for _ in range(12)])


def generate_product_name() -> str:
    """Generate a realistic product name."""
    template, _, _, _ = random.choice(PRODUCT_TEMPLATES)
    adj = random.choice(ADJECTIVES)
    return template.format(adj=adj)


def get_template_for_name(name: str) -> tuple:
    """Find matching template for a product name."""
    for template, category, weight_range, price_range in PRODUCT_TEMPLATES:
        # Check if this could be our template
        base = template.replace("{adj} ", "").replace(" {adj}", "").replace("{adj}", "")
        if any(word in name for word in base.split()[:2]):
            return template, category, weight_range, price_range
    return PRODUCT_TEMPLATES[0]


class ProductFactory(AsyncSQLAlchemyFactory):
    """Factory for Product model with realistic e-commerce data."""

    class Meta:
        model = Product

    tenant_id = None
    sku = factory.LazyFunction(generate_sku)
    product_type = ProductType.SIMPLE
    status = ProductStatus.ACTIVE

    name = factory.LazyFunction(generate_product_name)
    brand = factory.LazyFunction(lambda: random.choice(BRANDS))
    manufacturer = factory.LazyAttribute(lambda o: o.brand)
    model_number = factory.LazyFunction(lambda: f"MDL-{random.randint(1000, 9999)}")

    upc = factory.LazyFunction(generate_upc)
    asin = factory.LazyFunction(lambda: "B0" + "".join(random.choices("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", k=8)))

    short_description = factory.LazyAttribute(
        lambda o: f"High-quality {o.name.lower()} from {o.brand}. Perfect for everyday use."
    )
    long_description = factory.LazyAttribute(
        lambda o: f"""Introducing the {o.name} by {o.brand}.

This premium product is designed with quality and durability in mind. Features include:
- Premium materials for long-lasting performance
- Modern design that fits any setting  
- Easy to use and maintain
- Backed by our satisfaction guarantee

Whether you're a professional or hobbyist, this product delivers exceptional value."""
    )
    bullet_points = factory.LazyAttribute(
        lambda o: [
            f"Premium quality from {o.brand}",
            "Durable construction for long-lasting use",
            "Modern ergonomic design",
            "Easy setup and maintenance",
            "100% satisfaction guaranteed",
        ]
    )
    search_terms = factory.LazyAttribute(
        lambda o: [o.brand.lower(), o.name.split()[0].lower(), "premium", "best seller"]
    )

    # Physical attributes - realistic ranges based on product type
    weight_value = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(0.5, 10.0), 2))))
    weight_unit = "lb"
    length_value = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(4, 24), 1))))
    width_value = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(4, 18), 1))))
    height_value = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(2, 12), 1))))
    dimension_unit = "in"

    # Package dimensions (slightly larger)
    pkg_weight_value = factory.LazyAttribute(lambda o: o.weight_value + Decimal("0.5"))
    pkg_length_value = factory.LazyAttribute(lambda o: o.length_value + Decimal("2"))
    pkg_width_value = factory.LazyAttribute(lambda o: o.width_value + Decimal("2"))
    pkg_height_value = factory.LazyAttribute(lambda o: o.height_value + Decimal("2"))

    country_of_origin = factory.LazyFunction(lambda: random.choice(["CN", "US", "MX", "VN", "TW"]))
    hazmat = False

    # Pricing
    cost_price = factory.LazyFunction(lambda: Decimal(str(round(random.uniform(5, 100), 2))))
    msrp = factory.LazyAttribute(lambda o: o.cost_price * Decimal("2.5"))

    class Params:
        draft = factory.Trait(status=ProductStatus.DRAFT)
        archived = factory.Trait(status=ProductStatus.ARCHIVED)


class VariationProductFactory(ProductFactory):
    """Factory for product variations (child products)."""

    product_type = ProductType.VARIATION
    
    variation_type = factory.LazyFunction(lambda: random.choice(["Color", "Size", "Style"]))
    variation_value = factory.LazyAttribute(
        lambda o: random.choice(
            ["Red", "Blue", "Black", "White", "Green"] if o.variation_type == "Color"
            else ["Small", "Medium", "Large", "XL", "XXL"] if o.variation_type == "Size"
            else ["Modern", "Classic", "Sport", "Premium"]
        )
    )


class ProductImageFactory(AsyncSQLAlchemyFactory):
    """Factory for ProductImage model."""

    class Meta:
        model = ProductImage

    product_id = None
    url = factory.LazyFunction(
        lambda: f"https://picsum.photos/seed/{random.randint(1, 10000)}/800/800"
    )
    alt_text = factory.LazyFunction(lambda: f"Product image {random.randint(1, 100)}")
    position = factory.Sequence(lambda n: n)
    width = 800
    height = 800
    mime_type = "image/jpeg"


class ProductAttributeFactory(AsyncSQLAlchemyFactory):
    """Factory for ProductAttribute model."""

    class Meta:
        model = ProductAttribute

    product_id = None
    name = factory.LazyFunction(lambda: random.choice([
        "Material", "Color", "Warranty", "Compatibility", "Power Source",
        "Capacity", "Connectivity", "Battery Life", "Rating"
    ]))
    value = factory.LazyAttribute(
        lambda o: {
            "Material": random.choice(["Plastic", "Metal", "Wood", "Fabric", "Silicone"]),
            "Color": random.choice(["Black", "White", "Silver", "Blue", "Red"]),
            "Warranty": random.choice(["1 Year", "2 Years", "Lifetime", "90 Days"]),
            "Compatibility": random.choice(["Universal", "iOS/Android", "Windows/Mac"]),
            "Power Source": random.choice(["Battery", "USB", "AC Adapter", "Solar"]),
            "Capacity": random.choice(["16GB", "32GB", "64GB", "128GB"]),
            "Connectivity": random.choice(["Bluetooth 5.0", "WiFi", "USB-C", "Lightning"]),
            "Battery Life": random.choice(["8 hours", "12 hours", "24 hours", "48 hours"]),
            "Rating": random.choice(["4.5 stars", "4.7 stars", "4.8 stars", "5 stars"]),
        }.get(o.name, "Standard")
    )
    group = factory.LazyAttribute(
        lambda o: "Specifications" if o.name in ["Material", "Capacity", "Connectivity"] else "Features"
    )
