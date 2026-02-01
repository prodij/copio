"""Category factory."""

import random

import factory
from faker import Faker

from src.db.models.category import Category, ProductCategory
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# Realistic category hierarchy
CATEGORY_TREE = {
    "Electronics": ["Audio", "Computers", "Mobile", "Accessories", "Gaming"],
    "Home & Garden": ["Furniture", "Kitchen", "Bedding", "Decor", "Garden"],
    "Sports & Fitness": ["Exercise Equipment", "Outdoor Recreation", "Team Sports", "Yoga"],
    "Office Supplies": ["Desk Accessories", "Organization", "Writing", "Tech"],
    "Pet Supplies": ["Dog", "Cat", "Fish", "Bird", "Small Animals"],
    "Beauty & Personal Care": ["Skincare", "Haircare", "Makeup", "Fragrance"],
    "Tools & Hardware": ["Power Tools", "Hand Tools", "Safety", "Storage"],
    "Automotive": ["Accessories", "Parts", "Tools", "Care"],
}


def generate_slug(name: str) -> str:
    """Generate a URL-friendly slug."""
    return name.lower().replace(" ", "-").replace("&", "and").replace("'", "")


class CategoryFactory(AsyncSQLAlchemyFactory):
    """Factory for Category model."""

    class Meta:
        model = Category

    tenant_id = None
    name = factory.LazyFunction(lambda: random.choice(list(CATEGORY_TREE.keys())))
    slug = factory.LazyAttribute(lambda o: generate_slug(o.name) + f"-{random.randint(100, 999)}")
    parent_id = None
    description = factory.LazyAttribute(
        lambda o: f"Browse our selection of {o.name.lower()} products."
    )

    # Channel mappings
    amazon_browse_node = factory.LazyFunction(lambda: str(random.randint(100000, 999999)))
    shopify_product_type = factory.LazyAttribute(lambda o: o.name)


class ProductCategoryFactory(AsyncSQLAlchemyFactory):
    """Factory for ProductCategory junction."""

    class Meta:
        model = ProductCategory

    product_id = None
    category_id = None
    is_primary = True
