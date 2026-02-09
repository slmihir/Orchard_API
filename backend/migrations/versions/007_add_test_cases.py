"""add_test_cases

Revision ID: 007_add_test_cases
Revises: 5a9d6e11f9b0
Create Date: 2026-01-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '007_add_test_cases'
down_revision: Union[str, None] = '5a9d6e11f9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'test_cases',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('page_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('discovered_pages.id'), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('instruction', sa.Text, nullable=False),
        sa.Column('steps', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('test_type', sa.String(50), nullable=False, server_default='positive'),
        sa.Column('source', sa.String(50), nullable=False, server_default='suggested'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('last_run_at', sa.DateTime, nullable=True),
        sa.Column('last_run_status', sa.String(50), nullable=True),
        sa.Column('last_run_duration', sa.Integer, nullable=True),
        sa.Column('last_run_error', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_test_cases_project_id', 'test_cases', ['project_id'])
    op.create_index('ix_test_cases_page_id', 'test_cases', ['page_id'])

    op.create_table(
        'test_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('test_case_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('test_cases.id'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, server_default='queued'),
        sa.Column('started_at', sa.DateTime, nullable=True),
        sa.Column('completed_at', sa.DateTime, nullable=True),
        sa.Column('duration', sa.Integer, nullable=True),
        sa.Column('steps_completed', sa.Integer, nullable=False, server_default='0'),
        sa.Column('steps_total', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('error_step', sa.Integer, nullable=True),
        sa.Column('logs', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('screenshots', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_test_runs_test_case_id', 'test_runs', ['test_case_id'])
    op.create_index('ix_test_runs_project_id', 'test_runs', ['project_id'])


def downgrade() -> None:
    op.drop_table('test_runs')
    op.drop_table('test_cases')
