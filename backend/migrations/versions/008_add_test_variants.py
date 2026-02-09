"""add_test_variants

Revision ID: 008_add_test_variants
Revises: 007_add_test_cases
Create Date: 2026-01-21
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '008_add_test_variants'
down_revision = '007_add_test_cases'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tests', sa.Column('parent_test_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('tests', sa.Column('variant_type', sa.String(50), nullable=True))
    op.add_column('tests', sa.Column('expected_result', sa.Text(), nullable=True))

    op.create_foreign_key(
        'fk_tests_parent_test_id',
        'tests', 'tests',
        ['parent_test_id'], ['id'],
        ondelete='CASCADE'
    )

    op.create_index('ix_tests_parent_test_id', 'tests', ['parent_test_id'])


def downgrade() -> None:
    op.drop_index('ix_tests_parent_test_id', table_name='tests')
    op.drop_constraint('fk_tests_parent_test_id', 'tests', type_='foreignkey')
    op.drop_column('tests', 'expected_result')
    op.drop_column('tests', 'variant_type')
    op.drop_column('tests', 'parent_test_id')
