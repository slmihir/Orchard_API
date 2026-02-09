"""add_api_testing

Revision ID: 009_add_api_testing
Revises: 008_add_test_variants
Create Date: 2026-02-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '009_add_api_testing'
down_revision = '008_add_test_variants'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # API Collections table
    op.create_table(
        'api_collections',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('auth_config', postgresql.JSONB(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), nullable=True),
        sa.Column('default_headers', postgresql.JSONB(), nullable=True),
        sa.Column('default_engine', sa.String(20), nullable=False, server_default='python'),
        sa.Column('import_source', sa.String(50), nullable=True),
        sa.Column('import_source_id', sa.String(255), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_collections_user_id', 'api_collections', ['user_id'])
    op.create_index('ix_api_collections_org_id', 'api_collections', ['org_id'])
    op.create_foreign_key('fk_api_collections_user_id', 'api_collections', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_api_collections_org_id', 'api_collections', 'organizations', ['org_id'], ['id'])

    # API Environments table
    op.create_table(
        'api_environments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('variables', postgresql.JSONB(), nullable=True),
        sa.Column('base_url', sa.String(500), nullable=True),
        sa.Column('auth_config', postgresql.JSONB(), nullable=True),
        sa.Column('default_headers', postgresql.JSONB(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_environments_collection_id', 'api_environments', ['collection_id'])
    op.create_index('ix_api_environments_user_id', 'api_environments', ['user_id'])
    op.create_index('ix_api_environments_org_id', 'api_environments', ['org_id'])
    op.create_foreign_key('fk_api_environments_collection_id', 'api_environments', 'api_collections', ['collection_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_api_environments_user_id', 'api_environments', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_api_environments_org_id', 'api_environments', 'organizations', ['org_id'], ['id'])

    # API Requests table
    op.create_table(
        'api_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('order_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('method', sa.String(10), nullable=False),
        sa.Column('url_path', sa.String(1000), nullable=False),
        sa.Column('headers', postgresql.JSONB(), nullable=True),
        sa.Column('query_params', postgresql.JSONB(), nullable=True),
        sa.Column('body', postgresql.JSONB(), nullable=True),
        sa.Column('assertions', postgresql.JSONB(), nullable=True),
        sa.Column('variable_extractions', postgresql.JSONB(), nullable=True),
        sa.Column('pre_request_script', sa.Text(), nullable=True),
        sa.Column('pre_request_script_type', sa.String(20), nullable=True),
        sa.Column('post_response_script', sa.Text(), nullable=True),
        sa.Column('post_response_script_type', sa.String(20), nullable=True),
        sa.Column('engine', sa.String(20), nullable=True),
        sa.Column('folder_path', sa.String(500), nullable=True),
        sa.Column('timeout_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_requests_collection_id', 'api_requests', ['collection_id'])
    op.create_foreign_key('fk_api_requests_collection_id', 'api_requests', 'api_collections', ['collection_id'], ['id'], ondelete='CASCADE')

    # API Test Runs table
    op.create_table(
        'api_test_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=True),
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('trigger_source', sa.String(255), nullable=True),
        sa.Column('environment_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('engine', sa.String(20), nullable=False, server_default='python'),
        sa.Column('status', sa.String(50), nullable=False, server_default='pending'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        sa.Column('total_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('passed_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_requests', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_assertions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('passed_assertions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_assertions', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('run_context', postgresql.JSONB(), nullable=True),
        sa.Column('karate_job_id', sa.String(100), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_test_runs_collection_id', 'api_test_runs', ['collection_id'])
    op.create_index('ix_api_test_runs_user_id', 'api_test_runs', ['user_id'])
    op.create_index('ix_api_test_runs_org_id', 'api_test_runs', ['org_id'])
    op.create_foreign_key('fk_api_test_runs_collection_id', 'api_test_runs', 'api_collections', ['collection_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_api_test_runs_environment_id', 'api_test_runs', 'api_environments', ['environment_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_api_test_runs_user_id', 'api_test_runs', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_api_test_runs_org_id', 'api_test_runs', 'organizations', ['org_id'], ['id'])

    # API Request Results table
    op.create_table(
        'api_request_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('test_run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('execution_order', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('resolved_url', sa.String(2000), nullable=True),
        sa.Column('resolved_method', sa.String(10), nullable=True),
        sa.Column('resolved_headers', postgresql.JSONB(), nullable=True),
        sa.Column('resolved_body', sa.Text(), nullable=True),
        sa.Column('response_status', sa.Integer(), nullable=True),
        sa.Column('response_headers', postgresql.JSONB(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('response_size_bytes', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('timing_breakdown', postgresql.JSONB(), nullable=True),
        sa.Column('assertion_results', postgresql.JSONB(), nullable=True),
        sa.Column('extracted_variables', postgresql.JSONB(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_type', sa.String(100), nullable=True),
        sa.Column('pre_script_executed', sa.Boolean(), nullable=True),
        sa.Column('pre_script_error', sa.Text(), nullable=True),
        sa.Column('post_script_executed', sa.Boolean(), nullable=True),
        sa.Column('post_script_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_api_request_results_test_run_id', 'api_request_results', ['test_run_id'])
    op.create_index('ix_api_request_results_request_id', 'api_request_results', ['request_id'])
    op.create_foreign_key('fk_api_request_results_test_run_id', 'api_request_results', 'api_test_runs', ['test_run_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_api_request_results_request_id', 'api_request_results', 'api_requests', ['request_id'], ['id'], ondelete='CASCADE')

    # Karate Feature Files table
    op.create_table(
        'karate_feature_files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('collection_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('feature_content', sa.Text(), nullable=False),
        sa.Column('parsed_metadata', postgresql.JSONB(), nullable=True),
        sa.Column('config_content', sa.Text(), nullable=True),
        sa.Column('additional_files', postgresql.JSONB(), nullable=True),
        sa.Column('tags', postgresql.JSONB(), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_karate_feature_files_collection_id', 'karate_feature_files', ['collection_id'])
    op.create_index('ix_karate_feature_files_user_id', 'karate_feature_files', ['user_id'])
    op.create_index('ix_karate_feature_files_org_id', 'karate_feature_files', ['org_id'])
    op.create_foreign_key('fk_karate_feature_files_collection_id', 'karate_feature_files', 'api_collections', ['collection_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_karate_feature_files_user_id', 'karate_feature_files', 'users', ['user_id'], ['id'])
    op.create_foreign_key('fk_karate_feature_files_org_id', 'karate_feature_files', 'organizations', ['org_id'], ['id'])


def downgrade() -> None:
    # Drop tables in reverse order of creation (respecting foreign key dependencies)
    op.drop_table('karate_feature_files')
    op.drop_table('api_request_results')
    op.drop_table('api_test_runs')
    op.drop_table('api_requests')
    op.drop_table('api_environments')
    op.drop_table('api_collections')
