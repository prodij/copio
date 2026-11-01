from alembic import context

import app.models_registry  # noqa: F401  (imports every model so autogenerate sees them)
from app.config import get_settings
from app.db import Base, engine_for

target_metadata = Base.metadata

with engine_for(get_settings().database_url).connect() as connection:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()
