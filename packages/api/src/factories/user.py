"""User factory."""

import factory
from faker import Faker
from passlib.hash import argon2

from src.db.models.user import User
from src.factories.base import AsyncSQLAlchemyFactory

fake = Faker()

# Pre-hash a common password for efficiency
DEFAULT_PASSWORD_HASH = argon2.hash("test1234")


class UserFactory(AsyncSQLAlchemyFactory):
    """Factory for User model."""

    class Meta:
        model = User

    email = factory.LazyFunction(lambda: fake.unique.email())
    hashed_password = DEFAULT_PASSWORD_HASH
    first_name = factory.LazyFunction(lambda: fake.first_name())
    last_name = factory.LazyFunction(lambda: fake.last_name())
    role = "member"
    is_active = True
    is_superuser = False
    is_verified = True

    # tenant_id must be provided or set via SubFactory
    tenant_id = None

    class Params:
        admin = factory.Trait(
            role="admin",
            is_superuser=True,
        )
