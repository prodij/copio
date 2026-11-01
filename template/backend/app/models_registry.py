"""Imports every model module so Alembic sees all tables."""
import app.billing.models
import app.workspaces.models  # noqa: F401
