"""add_admin_audit_log_table

Revision ID: 472672172428
Revises: aa241d974370
Create Date: 2026-02-04 13:01:24.807461

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '472672172428'
down_revision: Union[str, None] = 'aa241d974370'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'admin_audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('admin_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_type', sa.String(length=50), nullable=False),
        sa.Column('target_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('target_label', sa.String(length=255), nullable=False),
        sa.Column('before_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('after_state', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=False),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('impersonating_user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['admin_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['impersonating_user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_admin_audit_log_action', 'admin_audit_log', ['action', 'created_at'], unique=False)
    op.create_index('idx_admin_audit_log_admin', 'admin_audit_log', ['admin_id', 'created_at'], unique=False)
    op.create_index('idx_admin_audit_log_target', 'admin_audit_log', ['target_type', 'target_id'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_admin_audit_log_target', table_name='admin_audit_log')
    op.drop_index('idx_admin_audit_log_admin', table_name='admin_audit_log')
    op.drop_index('idx_admin_audit_log_action', table_name='admin_audit_log')
    op.drop_table('admin_audit_log')
