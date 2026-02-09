"""Add multi-tenancy support with organizations, user_id and org_id

Revision ID: 004_add_multi_tenancy
Revises: 003_add_user_settings
Create Date: 2025-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '004_add_multi_tenancy'
down_revision: Union[str, None] = '003_add_user_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    op.add_column('users', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_users_org_id', 'users', ['org_id'])
    op.create_foreign_key('fk_users_org_id', 'users', 'organizations', ['org_id'], ['id'])

    op.add_column('collections', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('collections', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_collections_user_id', 'collections', ['user_id'])
    op.create_index('ix_collections_org_id', 'collections', ['org_id'])
    op.create_foreign_key('fk_collections_user_id', 'collections', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_collections_org_id', 'collections', 'organizations', ['org_id'], ['id'])

    op.add_column('tests', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('tests', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_tests_user_id', 'tests', ['user_id'])
    op.create_index('ix_tests_org_id', 'tests', ['org_id'])
    op.create_foreign_key('fk_tests_user_id', 'tests', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_tests_org_id', 'tests', 'organizations', ['org_id'], ['id'])

    op.add_column('schedules', sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('schedules', sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_schedules_user_id', 'schedules', ['user_id'])
    op.create_index('ix_schedules_org_id', 'schedules', ['org_id'])
    op.create_foreign_key('fk_schedules_user_id', 'schedules', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_schedules_org_id', 'schedules', 'organizations', ['org_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_schedules_org_id', 'schedules', type_='foreignkey')
    op.drop_constraint('fk_schedules_user_id', 'schedules', type_='foreignkey')
    op.drop_index('ix_schedules_org_id', 'schedules')
    op.drop_index('ix_schedules_user_id', 'schedules')
    op.drop_column('schedules', 'org_id')
    op.drop_column('schedules', 'user_id')

    op.drop_constraint('fk_tests_org_id', 'tests', type_='foreignkey')
    op.drop_constraint('fk_tests_user_id', 'tests', type_='foreignkey')
    op.drop_index('ix_tests_org_id', 'tests')
    op.drop_index('ix_tests_user_id', 'tests')
    op.drop_column('tests', 'org_id')
    op.drop_column('tests', 'user_id')

    op.drop_constraint('fk_collections_org_id', 'collections', type_='foreignkey')
    op.drop_constraint('fk_collections_user_id', 'collections', type_='foreignkey')
    op.drop_index('ix_collections_org_id', 'collections')
    op.drop_index('ix_collections_user_id', 'collections')
    op.drop_column('collections', 'org_id')
    op.drop_column('collections', 'user_id')

    op.drop_constraint('fk_users_org_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_org_id', 'users')
    op.drop_column('users', 'org_id')

    op.drop_index('ix_organizations_slug', 'organizations')
    op.drop_table('organizations')
