"""Add user_settings table for configurable healing

Revision ID: 003_add_user_settings
Revises: 002_add_healing_suggestions
Create Date: 2024-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003_add_user_settings'
down_revision: Union[str, None] = '002_add_healing_suggestions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_settings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),

        # Healing settings
        sa.Column('healing_enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('healing_auto_approve', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('healing_auto_approve_threshold', sa.Float(), nullable=False, server_default='0.85'),
        sa.Column('healing_mode', sa.String(20), nullable=False, server_default='inline'),
        sa.Column('healing_provider', sa.String(20), nullable=False, server_default='gemini'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),

        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id')
    )


def downgrade() -> None:
    op.drop_table('user_settings')
