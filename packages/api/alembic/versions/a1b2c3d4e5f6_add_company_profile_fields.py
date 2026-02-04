"""Add company profile fields to tenants.

Revision ID: a1b2c3d4e5f6
Revises: 8700014c0d8f
Create Date: 2026-02-01 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '8700014c0d8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Company identity
    op.add_column('tenants', sa.Column('company_name', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('legal_name', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('tax_id', sa.String(50), nullable=True))
    
    # Address
    op.add_column('tenants', sa.Column('address_line1', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('address_line2', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('city', sa.String(100), nullable=True))
    op.add_column('tenants', sa.Column('state', sa.String(100), nullable=True))
    op.add_column('tenants', sa.Column('postal_code', sa.String(20), nullable=True))
    op.add_column('tenants', sa.Column('country', sa.String(2), nullable=True, server_default='US'))
    
    # Contact
    op.add_column('tenants', sa.Column('phone', sa.String(30), nullable=True))
    op.add_column('tenants', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('tenants', sa.Column('website', sa.String(255), nullable=True))
    
    # Branding (for POs/invoices)
    op.add_column('tenants', sa.Column('logo_url', sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column('tenants', 'logo_url')
    op.drop_column('tenants', 'website')
    op.drop_column('tenants', 'email')
    op.drop_column('tenants', 'phone')
    op.drop_column('tenants', 'country')
    op.drop_column('tenants', 'postal_code')
    op.drop_column('tenants', 'state')
    op.drop_column('tenants', 'city')
    op.drop_column('tenants', 'address_line2')
    op.drop_column('tenants', 'address_line1')
    op.drop_column('tenants', 'tax_id')
    op.drop_column('tenants', 'legal_name')
    op.drop_column('tenants', 'company_name')
