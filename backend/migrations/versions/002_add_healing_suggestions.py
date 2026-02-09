"""Add healing_suggestions table for self-healing feature

Revision ID: 002_add_healing_suggestions
Revises: 001_initial
Create Date: 2024-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_healing_suggestions'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'healing_suggestions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_index', sa.Integer(), nullable=False),

        # Original vs suggested selector
        sa.Column('original_selector', sa.String(500), nullable=False),
        sa.Column('suggested_selector', sa.String(500), nullable=False),
        sa.Column('alternative_selectors', postgresql.JSONB(), nullable=True),

        # LLM analysis
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('reasoning', sa.Text(), nullable=True),
        sa.Column('selector_type', sa.String(20), nullable=False, server_default='css'),

        # Context snapshot
        sa.Column('context_snapshot', postgresql.JSONB(), nullable=True),
        sa.Column('screenshot_b64', sa.Text(), nullable=True),

        # Status
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('auto_approved', sa.Boolean(), nullable=False, server_default='false'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('applied_at', sa.DateTime(), nullable=True),

        # Retry result
        sa.Column('retry_success', sa.Boolean(), nullable=True),

        sa.ForeignKeyConstraint(['run_id'], ['runs.id']),
        sa.ForeignKeyConstraint(['step_id'], ['steps.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Index for quick lookup by run
    op.create_index('ix_healing_suggestions_run_id', 'healing_suggestions', ['run_id'])
    op.create_index('ix_healing_suggestions_status', 'healing_suggestions', ['status'])


def downgrade() -> None:
    op.drop_index('ix_healing_suggestions_status', table_name='healing_suggestions')
    op.drop_index('ix_healing_suggestions_run_id', table_name='healing_suggestions')
    op.drop_table('healing_suggestions')
