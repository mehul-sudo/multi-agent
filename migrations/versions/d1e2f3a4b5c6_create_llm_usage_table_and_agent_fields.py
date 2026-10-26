"""create llm_usage table and agent llm fields

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-09-13 13:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1e2f3a4b5c6'
down_revision = 'c1d2e3f4a5b6'
branch_labels = None
depends_on = None


def upgrade():
    # ### Add LLM columns to agents table ###
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('provider', sa.String(length=50), nullable=False, server_default='mock'))
        batch_op.add_column(sa.Column('model', sa.String(length=100), nullable=False, server_default='mock-v1'))
        batch_op.add_column(sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'))
        batch_op.add_column(sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='1000'))
        batch_op.add_column(sa.Column('token_budget', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('cost_budget', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('fallback_provider', sa.String(length=50), nullable=True))

    # ### Create llm_usage_logs table ###
    op.create_table(
        'llm_usage_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('workflow_execution_id', sa.Integer(), nullable=True),
        sa.Column('task_execution_id', sa.Integer(), nullable=True),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('total_tokens', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('estimated_cost_usd', sa.Float(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_category', sa.String(length=100), nullable=True),
        sa.Column('fallback_used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['workflow_execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_execution_id'], ['task_executions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('llm_usage_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_agent_id'), ['agent_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_workflow_execution_id'), ['workflow_execution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_task_execution_id'), ['task_execution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_provider'), ['provider'], unique=False)
        batch_op.create_index(batch_op.f('ix_llm_usage_logs_model'), ['model'], unique=False)


def downgrade():
    op.drop_table('llm_usage_logs')
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_column('fallback_provider')
        batch_op.drop_column('cost_budget')
        batch_op.drop_column('token_budget')
        batch_op.drop_column('max_tokens')
        batch_op.drop_column('temperature')
        batch_op.drop_column('model')
        batch_op.drop_column('provider')
