"""create phase5 orchestration tables

Revision ID: c1d2e3f4a5b6
Revises: a1b2c3d4e5f6
Create Date: 2026-09-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c1d2e3f4a5b6'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # ### Agents table ###
    op.create_table(
        'agents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('system_instructions', sa.Text(), nullable=False),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('capabilities', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('active', 'disabled', 'archived')", name='ck_agents_status_valid'),
    )
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agents_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_agents_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_agents_agent_type'), ['agent_type'], unique=False)

    # ### Workflows table ###
    op.create_table(
        'workflows',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('input_schema', sa.JSON(), nullable=False),
        sa.Column('output_schema', sa.JSON(), nullable=False),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('draft', 'active', 'archived', 'disabled')", name='ck_workflows_status_valid'),
    )
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflows_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflows_user_id'), ['user_id'], unique=False)

    # ### Workflow Nodes table ###
    op.create_table(
        'workflow_nodes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('input_mapping', sa.JSON(), nullable=False),
        sa.Column('output_key', sa.String(length=100), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False),
        sa.Column('retry_limit', sa.Integer(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('position', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('workflow_nodes', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_nodes_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_nodes_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_nodes_agent_id'), ['agent_id'], unique=False)

    # ### Workflow Dependencies table ###
    op.create_table(
        'workflow_dependencies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('source_node_id', sa.Integer(), nullable=False),
        sa.Column('target_node_id', sa.Integer(), nullable=False),
        sa.Column('dependency_type', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_node_id'], ['workflow_nodes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_node_id'], ['workflow_nodes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_node_id', 'target_node_id', name='uq_workflow_dependencies_source_target'),
        sa.CheckConstraint('source_node_id != target_node_id', name='ck_workflow_dependencies_no_self_loop'),
        sa.CheckConstraint("dependency_type IN ('on_success', 'on_failure', 'always')", name='ck_workflow_dependencies_type_valid'),
    )
    with op.batch_alter_table('workflow_dependencies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_dependencies_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_dependencies_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_dependencies_source_node_id'), ['source_node_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_dependencies_target_node_id'), ['target_node_id'], unique=False)

    # ### Workflow Executions table ###
    op.create_table(
        'workflow_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('triggered_by', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('output_data', sa.JSON(), nullable=False),
        sa.Column('context_data', sa.JSON(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('queued', 'running', 'paused', 'completed', 'failed', 'cancelled', 'partially_completed')", name='ck_workflow_executions_status_valid'),
    )
    with op.batch_alter_table('workflow_executions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_executions_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_executions_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_executions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_executions_idempotency_key'), ['idempotency_key'], unique=False)

    # ### Task Executions table ###
    op.create_table(
        'task_executions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_execution_id', sa.Integer(), nullable=False),
        sa.Column('workflow_node_id', sa.Integer(), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('attempt_number', sa.Integer(), nullable=False),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('output_data', sa.JSON(), nullable=False),
        sa.Column('error_data', sa.JSON(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['workflow_execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_node_id'], ['workflow_nodes.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint("status IN ('pending', 'blocked', 'ready', 'running', 'retrying', 'completed', 'failed', 'skipped', 'cancelled')", name='ck_task_executions_status_valid'),
    )
    with op.batch_alter_table('task_executions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_task_executions_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_task_executions_workflow_execution_id'), ['workflow_execution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_executions_workflow_node_id'), ['workflow_node_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_task_executions_agent_id'), ['agent_id'], unique=False)

    # ### Audit Events table ###
    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('event_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_audit_events_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_audit_events_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_resource_type'), ['resource_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_resource_id'), ['resource_id'], unique=False)


def downgrade():
    op.drop_table('audit_events')
    op.drop_table('task_executions')
    op.drop_table('workflow_executions')
    op.drop_table('workflow_dependencies')
    op.drop_table('workflow_nodes')
    op.drop_table('workflows')
    op.drop_table('agents')
