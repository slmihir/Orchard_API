"""Add RBAC with roles and permissions

Revision ID: 005_add_rbac
Revises: 004_add_multi_tenancy
Create Date: 2025-01-17

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '005_add_rbac'
down_revision: Union[str, None] = '004_add_multi_tenancy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Default role definitions
DEFAULT_ROLES = {
    "admin": {
        "display_name": "Administrator",
        "description": "Full system access",
        "permissions": {
            "manage_users": True,
            "manage_org": True,
            "manage_roles": True,
            "manage_tests": True,
            "run_tests": True,
            "view_tests": True,
            "manage_schedules": True,
            "view_schedules": True,
            "manage_settings": True,
            "view_dashboard": True,
            "view_admin_dashboard": True,
        },
        "is_system": True,
    },
    "member": {
        "display_name": "Member",
        "description": "Standard team member access",
        "permissions": {
            "manage_users": False,
            "manage_org": False,
            "manage_roles": False,
            "manage_tests": True,
            "run_tests": True,
            "view_tests": True,
            "manage_schedules": True,
            "view_schedules": True,
            "manage_settings": False,
            "view_dashboard": True,
            "view_admin_dashboard": False,
        },
        "is_system": True,
    },
    "viewer": {
        "display_name": "Viewer",
        "description": "Read-only access",
        "permissions": {
            "manage_users": False,
            "manage_org": False,
            "manage_roles": False,
            "manage_tests": False,
            "run_tests": False,
            "view_tests": True,
            "manage_schedules": False,
            "view_schedules": True,
            "manage_settings": False,
            "view_dashboard": True,
            "view_admin_dashboard": False,
        },
        "is_system": True,
    },
}


def upgrade() -> None:
    op.create_table(
        'roles',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('permissions', postgresql.JSONB(), nullable=False, server_default='{}'),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    op.add_column('users', sa.Column('role_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index('ix_users_role_id', 'users', ['role_id'])
    op.create_foreign_key('fk_users_role_id', 'users', 'roles', ['role_id'], ['id'])

    # Insert default roles
    roles_table = sa.table(
        'roles',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('name', sa.String(50)),
        sa.column('display_name', sa.String(100)),
        sa.column('description', sa.String(255)),
        sa.column('permissions', postgresql.JSONB()),
        sa.column('is_system', sa.Boolean()),
    )

    role_ids = {}
    for role_name, role_data in DEFAULT_ROLES.items():
        role_id = uuid.uuid4()
        role_ids[role_name] = role_id
        op.execute(
            roles_table.insert().values(
                id=role_id,
                name=role_name,
                display_name=role_data['display_name'],
                description=role_data['description'],
                permissions=role_data['permissions'],
                is_system=role_data['is_system'],
            )
        )

    # Assign 'member' role to all existing users
    users_table = sa.table(
        'users',
        sa.column('id', postgresql.UUID(as_uuid=True)),
        sa.column('role_id', postgresql.UUID(as_uuid=True)),
    )
    op.execute(
        users_table.update().values(role_id=role_ids['member'])
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_role_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_role_id', 'users')
    op.drop_column('users', 'role_id')

    # Drop roles table
    op.drop_table('roles')
