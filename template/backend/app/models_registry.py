"""Imports every model module so Alembic sees all tables."""
import app.audit.models
import app.billing.models
import app.connectors.models
import app.workspaces.models  # noqa: F401
