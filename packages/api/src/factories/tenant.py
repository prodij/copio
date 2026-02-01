"""Tenant factory."""

import factory
from faker import Faker

from src.db.models.tenant import Tenant
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()


class TenantFactory(AsyncSQLAlchemyFactory):
    """Factory for Tenant model."""

    class Meta:
        model = Tenant

    name = factory.LazyFunction(lambda: fake.company())
    slug = factory.LazyAttribute(lambda o: o.name.lower().replace(" ", "-").replace(",", "")[:50])
    timezone = "America/Los_Angeles"
    base_currency = "USD"
    settings = factory.LazyFunction(lambda: {"theme": "light", "notifications": True})
