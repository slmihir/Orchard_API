"""add_rich_page_analysis_fields

Revision ID: 5a9d6e11f9b0
Revises: 006_add_invitations
Create Date: 2026-01-17 13:58:05.768210

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '5a9d6e11f9b0'
down_revision: Union[str, None] = '006_add_invitations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Check if projects table exists, create if not
    projects_exists = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'projects')"
    )).scalar()
    
    if not projects_exists:
        # Create projects table
        op.create_table(
            'projects',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('base_url', sa.String(500), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('credentials', postgresql.JSONB(), nullable=True),
            sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
            sa.Column('discovery_started_at', sa.DateTime(), nullable=True),
            sa.Column('discovery_completed_at', sa.DateTime(), nullable=True),
            sa.Column('max_depth', sa.Integer(), nullable=False, server_default='5'),
            sa.Column('max_pages', sa.Integer(), nullable=False, server_default='100'),
            sa.Column('pages_discovered', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('features_found', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('patterns_detected', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index('ix_projects_user_id', 'projects', ['user_id'])
        op.create_index('ix_projects_org_id', 'projects', ['org_id'])
        op.create_foreign_key('fk_projects_user_id', 'projects', 'users', ['user_id'], ['id'])
        op.create_foreign_key('fk_projects_org_id', 'projects', 'organizations', ['org_id'], ['id'])
    
    # Check if discovered_pages table exists, create if not
    pages_exists = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'discovered_pages')"
    )).scalar()
    
    if not pages_exists:
        # Create discovered_pages table
        op.create_table(
            'discovered_pages',
            sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=False),
            sa.Column('url', sa.String(1000), nullable=False),
            sa.Column('path', sa.String(500), nullable=False),
            sa.Column('title', sa.String(500), nullable=True),
            sa.Column('page_type', sa.String(100), nullable=True),
            sa.Column('section', sa.String(255), nullable=True),
            sa.Column('state_hash', sa.String(64), nullable=True),
            sa.Column('screenshot_url', sa.String(500), nullable=True),
            sa.Column('thumbnail_url', sa.String(500), nullable=True),
            sa.Column('forms_found', postgresql.JSONB(), nullable=True),
            sa.Column('actions_found', postgresql.JSONB(), nullable=True),
            sa.Column('inputs_found', postgresql.JSONB(), nullable=True),
            sa.Column('nav_steps', postgresql.JSONB(), nullable=True),
            sa.Column('depth', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('is_pattern_instance', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('pattern_id', sa.String(100), nullable=True),
            sa.Column('is_feature', sa.Boolean(), nullable=False, server_default='false'),
            sa.Column('feature_name', sa.String(255), nullable=True),
            sa.Column('feature_description', sa.Text(), nullable=True),
            sa.Column('discovered_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('graph_x', sa.Float(), nullable=True),
            sa.Column('graph_y', sa.Float(), nullable=True),
            sa.Column('graph_z', sa.Float(), nullable=True),
        )
        op.create_index('ix_discovered_pages_state_hash', 'discovered_pages', ['state_hash'])
    
    # Now add the new columns if they don't exist
    columns_result = conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'discovered_pages'"
    )).fetchall()
    existing_columns = [row[0] for row in columns_result]
    
    if 'tables_found' not in existing_columns:
        op.add_column('discovered_pages', sa.Column('tables_found', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if 'llm_analysis' not in existing_columns:
        op.add_column('discovered_pages', sa.Column('llm_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if 'test_scenarios' not in existing_columns:
        op.add_column('discovered_pages', sa.Column('test_scenarios', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    if 'requires_auth' not in existing_columns:
        op.add_column('discovered_pages', sa.Column('requires_auth', sa.Boolean(), nullable=False, server_default='false'))
    if 'required_permissions' not in existing_columns:
        op.add_column('discovered_pages', sa.Column('required_permissions', postgresql.JSONB(astext_type=sa.Text()), nullable=True))


def downgrade() -> None:
    # Check if table exists before dropping columns using information_schema
    conn = op.get_bind()
    result = conn.execute(sa.text(
        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'discovered_pages')"
    )).scalar()
    
    if result:
        # Check if columns exist before dropping
        columns_result = conn.execute(sa.text(
            "SELECT column_name FROM information_schema.columns WHERE table_schema = 'public' AND table_name = 'discovered_pages'"
        )).fetchall()
        columns = [row[0] for row in columns_result]
        
        if 'required_permissions' in columns:
            op.drop_column('discovered_pages', 'required_permissions')
        if 'requires_auth' in columns:
            op.drop_column('discovered_pages', 'requires_auth')
        if 'test_scenarios' in columns:
            op.drop_column('discovered_pages', 'test_scenarios')
        if 'llm_analysis' in columns:
            op.drop_column('discovered_pages', 'llm_analysis')
        if 'tables_found' in columns:
            op.drop_column('discovered_pages', 'tables_found')
