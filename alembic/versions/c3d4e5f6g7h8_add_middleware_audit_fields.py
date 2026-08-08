"""Add middleware audit fields

Revision ID: c3d4e5f6g7h8
Revises: b2c3d4e5f6g7
Create Date: 2025-12-14 10:00:00.000000

Adds new columns to audit_logs table for middleware-based logging:
- http_method: GET, POST, PUT, DELETE
- request_body: Masked request body (truncated)
- query_params: Query string parameters
- response_status: HTTP status code
- response_time_ms: Response time in milliseconds
- response_body: Masked response body (truncated)
- is_middleware: Boolean flag to distinguish auto vs manual logs
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6g7h8'
down_revision = 'b2c3d4e5f6g7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns for middleware-based audit logging
    op.add_column('audit_logs', sa.Column('http_method', sa.String(10), nullable=True))
    op.add_column('audit_logs', sa.Column('request_body', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('query_params', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('response_status', sa.Integer(), nullable=True))
    op.add_column('audit_logs', sa.Column('response_time_ms', sa.Float(), nullable=True))
    op.add_column('audit_logs', sa.Column('response_body', sa.Text(), nullable=True))
    op.add_column('audit_logs', sa.Column('is_middleware', sa.Boolean(), nullable=False, server_default='false'))
    
    # Add indexes for common query patterns
    op.create_index('ix_audit_logs_http_method', 'audit_logs', ['http_method'])
    op.create_index('ix_audit_logs_response_status', 'audit_logs', ['response_status'])
    op.create_index('ix_audit_logs_endpoint', 'audit_logs', ['endpoint'])
    op.create_index('ix_audit_logs_is_middleware', 'audit_logs', ['is_middleware'])


def downgrade() -> None:
    # Remove indexes
    op.drop_index('ix_audit_logs_is_middleware', table_name='audit_logs')
    op.drop_index('ix_audit_logs_endpoint', table_name='audit_logs')
    op.drop_index('ix_audit_logs_response_status', table_name='audit_logs')
    op.drop_index('ix_audit_logs_http_method', table_name='audit_logs')
    
    # Remove columns
    op.drop_column('audit_logs', 'is_middleware')
    op.drop_column('audit_logs', 'response_body')
    op.drop_column('audit_logs', 'response_time_ms')
    op.drop_column('audit_logs', 'response_status')
    op.drop_column('audit_logs', 'query_params')
    op.drop_column('audit_logs', 'request_body')
    op.drop_column('audit_logs', 'http_method')

