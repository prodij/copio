"""add_tenant_status_fields

Revision ID: e8f9a1b2c3d4
Revises: 472672172428
Create Date: 2026-02-04 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e8f9a1b2c3d4'
down_revision: Union[str, None] = '472672172428'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('tenants', sa.Column('status', sa.String(length=20), server_default='active', nullable=False))
    op.add_column('tenants', sa.Column('suspended_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tenants', sa.Column('suspended_reason', sa.String(length=500), nullable=True))
    op.add_column('tenants', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'deleted_at')
    op.drop_column('tenants', 'suspended_reason')
    op.drop_column('tenants', 'suspended_at')
    op.drop_column('tenants', 'status')
