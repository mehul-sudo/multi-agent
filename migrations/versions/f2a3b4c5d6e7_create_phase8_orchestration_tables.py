"""create phase8 orchestration tables

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-09-13 14:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2a3b4c5d6e7'
down_revision = 'e1f2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    # ### Alter agents table for Phase 8 properties ###
    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('display_name', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('role', sa.String(length=50), nullable=False, server_default='Custom Specialized Agent'))
        batch_op.add_column(sa.Column('fallback_model', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('priority', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('max_concurrent_tasks', sa.Integer(), nullable=False, server_default='5'))
        batch_op.add_column(sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'))
        batch_op.add_column(sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'))
        batch_op.add_column(sa.Column('max_delegation_depth', sa.Integer(), nullable=False, server_default='3'))
        batch_op.add_column(sa.Column('requires_human_approval', sa.Boolean(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('allowed_tools', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('allowed_data_scopes', sa.JSON(), nullable=False, server_default='[]'))
        batch_op.add_column(sa.Column('budget_limits', sa.JSON(), nullable=False, server_default='{}'))

    # ### Create agent_versions table ###

    op.create_table(
        'agent_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=150), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('system_instructions', sa.Text(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='Custom Specialized Agent'),
        sa.Column('agent_type', sa.String(length=50), nullable=False, server_default='custom'),
        sa.Column('provider', sa.String(length=50), nullable=False, server_default='mock'),
        sa.Column('model', sa.String(length=100), nullable=False, server_default='mock-v1'),
        sa.Column('temperature', sa.Float(), nullable=False, server_default='0.7'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default='1000'),
        sa.Column('fallback_provider', sa.String(length=50), nullable=True),
        sa.Column('fallback_model', sa.String(length=100), nullable=True),
        sa.Column('configuration', sa.JSON(), nullable=False),
        sa.Column('capabilities', sa.JSON(), nullable=False),
        sa.Column('allowed_tools', sa.JSON(), nullable=False),
        sa.Column('allowed_data_scopes', sa.JSON(), nullable=False),
        sa.Column('budget_limits', sa.JSON(), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('max_concurrent_tasks', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_delegation_depth', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('requires_human_approval', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('agent_versions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_agent_versions_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_agent_versions_agent_id'), ['agent_id'], unique=False)

    # ### Create capabilities table ###
    op.create_table(
        'capabilities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=150), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema', sa.JSON(), nullable=False),
        sa.Column('output_schema', sa.JSON(), nullable=False),
        sa.Column('required_permissions', sa.JSON(), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='low'),
        sa.Column('required_tools', sa.JSON(), nullable=False),
        sa.Column('supported_data_types', sa.JSON(), nullable=False),
        sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_execution_time', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('requires_human_approval', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('capabilities', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_capabilities_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_capabilities_name'), ['name'], unique=True)

    # ### Create agent_capabilities table ###
    op.create_table(
        'agent_capabilities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('agent_id', sa.Integer(), nullable=False),
        sa.Column('capability_id', sa.Integer(), nullable=False),
        sa.Column('proficiency_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['capability_id'], ['capabilities.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create provider_configs table ###
    op.create_table(
        'provider_configs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('provider_name', sa.String(length=50), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=True),
        sa.Column('secret_key_ref', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('available_models', sa.JSON(), nullable=False),
        sa.Column('default_model', sa.String(length=100), nullable=True),
        sa.Column('model_capabilities', sa.JSON(), nullable=False),
        sa.Column('context_window_limits', sa.JSON(), nullable=False),
        sa.Column('rate_limits', sa.JSON(), nullable=False),
        sa.Column('cost_per_1k_tokens', sa.JSON(), nullable=False),
        sa.Column('fallback_priority', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('provider_configs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_provider_configs_public_id'), ['public_id'], unique=True)

    # ### Create orchestration_plans table ###
    op.create_table(
        'orchestration_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('assumptions', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('validation_status', sa.String(length=20), nullable=False, server_default='VALIDATED'),
        sa.Column('estimated_cost', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('estimated_duration', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_strategy', sa.String(length=50), nullable=False, server_default='REPLAN'),
        sa.Column('rollback_info', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('orchestration_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orchestration_plans_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_orchestration_plans_orchestration_id'), ['orchestration_id'], unique=False)

    # ### Create orchestration_sessions table ###
    op.create_table(
        'orchestration_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.String(length=100), nullable=True, server_default='default_org'),
        sa.Column('objective', sa.Text(), nullable=False),
        sa.Column('input_context', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='CREATED'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('root_task_id', sa.Integer(), nullable=True),
        sa.Column('parent_orchestration_id', sa.Integer(), nullable=True),
        sa.Column('correlation_id', sa.String(length=100), nullable=False),
        sa.Column('trace_id', sa.String(length=100), nullable=False),
        sa.Column('max_execution_time', sa.Integer(), nullable=False, server_default='3600'),
        sa.Column('max_agent_count', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('max_delegation_depth', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('max_total_tokens', sa.Integer(), nullable=False, server_default='100000'),
        sa.Column('max_total_cost', sa.Float(), nullable=False, server_default='10.0'),
        sa.Column('max_parallel_tasks', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('total_tokens_used', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_cost_incurred', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('requires_approval', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('approval_status', sa.String(length=20), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('result_summary', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['orchestration_plans.id']),
        sa.ForeignKeyConstraint(['parent_orchestration_id'], ['orchestration_sessions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('orchestration_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_orchestration_sessions_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_orchestration_sessions_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orchestration_sessions_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orchestration_sessions_correlation_id'), ['correlation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_orchestration_sessions_trace_id'), ['trace_id'], unique=False)

    # ### Create plan_tasks table ###
    op.create_table(
        'plan_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('task_key', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False, server_default='agent_task'),
        sa.Column('assigned_agent_id', sa.Integer(), nullable=True),
        sa.Column('assigned_agent_version', sa.Integer(), nullable=True),
        sa.Column('required_capabilities', sa.JSON(), nullable=False),
        sa.Column('input_references', sa.JSON(), nullable=False),
        sa.Column('output_schema', sa.JSON(), nullable=False),
        sa.Column('conditional_rules', sa.JSON(), nullable=False),
        sa.Column('retry_policy', sa.JSON(), nullable=False),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('approval_requirement', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('parent_task_id', sa.Integer(), nullable=True),
        sa.Column('delegation_depth', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_data', sa.JSON(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['orchestration_plans.id']),
        sa.ForeignKeyConstraint(['assigned_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['parent_task_id'], ['plan_tasks.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('plan_tasks', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plan_tasks_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_plan_tasks_plan_id'), ['plan_id'], unique=False)

    # ### Create task_dependencies table ###
    op.create_table(
        'task_dependencies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=False),
        sa.Column('parent_task_id', sa.Integer(), nullable=False),
        sa.Column('child_task_id', sa.Integer(), nullable=False),
        sa.Column('dependency_type', sa.String(length=20), nullable=False, server_default='required'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['plan_id'], ['orchestration_plans.id']),
        sa.ForeignKeyConstraint(['parent_task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['child_task_id'], ['plan_tasks.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create agent_messages table ###
    op.create_table(
        'agent_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('sender_agent_id', sa.Integer(), nullable=True),
        sa.Column('receiver_agent_id', sa.Integer(), nullable=True),
        sa.Column('message_type', sa.String(length=50), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=True),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('payload_schema', sa.JSON(), nullable=False),
        sa.Column('correlation_id', sa.String(length=100), nullable=False),
        sa.Column('reply_to_message_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='DELIVERED'),
        sa.Column('delivery_attempts', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('expiry_time', sa.DateTime(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['orchestration_plans.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['sender_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['receiver_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['reply_to_message_id'], ['agent_messages.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create shared_context_records table ###
    op.create_table(
        'shared_context_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('plan_id', sa.Integer(), nullable=True),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('scope', sa.String(length=30), nullable=False, server_default='GLOBAL'),
        sa.Column('key', sa.String(length=150), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('value_type', sa.String(length=30), nullable=False, server_default='json'),
        sa.Column('is_sensitive', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['plan_id'], ['orchestration_plans.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create context_versions table ###
    op.create_table(
        'context_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('context_record_id', sa.Integer(), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('value', sa.JSON(), nullable=False),
        sa.Column('updated_by_agent_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['context_record_id'], ['shared_context_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['updated_by_agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create delegation_records table ###
    op.create_table(
        'delegation_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('parent_task_id', sa.Integer(), nullable=False),
        sa.Column('child_task_id', sa.Integer(), nullable=False),
        sa.Column('parent_agent_id', sa.Integer(), nullable=False),
        sa.Column('child_agent_id', sa.Integer(), nullable=False),
        sa.Column('delegation_depth', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('delegation_reason', sa.Text(), nullable=True),
        sa.Column('requested_capability', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='IN_PROGRESS'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['parent_task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['child_task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['parent_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['child_agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create approval_requests table ###
    op.create_table(
        'approval_requests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('organization_id', sa.String(length=100), nullable=True, server_default='default_org'),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('requested_action', sa.String(length=150), nullable=False),
        sa.Column('risk_level', sa.String(length=20), nullable=False, server_default='medium'),
        sa.Column('explanation', sa.Text(), nullable=False),
        sa.Column('input_summary', sa.JSON(), nullable=False),
        sa.Column('proposed_output', sa.JSON(), nullable=False),
        sa.Column('requested_by_agent_id', sa.Integer(), nullable=True),
        sa.Column('assigned_approver_user_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
        sa.Column('expiry_time', sa.DateTime(), nullable=True),
        sa.Column('approval_comments', sa.Text(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('resolved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['requested_by_agent_id'], ['agents.id']),
        sa.ForeignKeyConstraint(['assigned_approver_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create orchestration_events table ###
    op.create_table(
        'orchestration_events',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('organization_id', sa.String(length=100), nullable=True, server_default='default_org'),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('agent_id', sa.Integer(), nullable=True),
        sa.Column('correlation_id', sa.String(length=100), nullable=False),
        sa.Column('trace_id', sa.String(length=100), nullable=False),
        sa.Column('actor', sa.String(length=100), nullable=False, server_default='system'),
        sa.Column('event_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create review_outcomes table ###
    op.create_table(
        'review_outcomes',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=False),
        sa.Column('reviewer_agent_id', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=30), nullable=False, server_default='Approved'),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('completeness_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('feedback', sa.Text(), nullable=True),
        sa.Column('validation_errors', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['reviewer_agent_id'], ['agents.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ### Create conflict_records table ###
    op.create_table(
        'conflict_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('orchestration_id', sa.Integer(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('conflicting_outputs', sa.JSON(), nullable=False),
        sa.Column('participating_agent_ids', sa.JSON(), nullable=False),
        sa.Column('evidence_references', sa.JSON(), nullable=False),
        sa.Column('resolution_strategy', sa.String(length=50), nullable=False, server_default='adjudicator_agent'),
        sa.Column('final_decision', sa.JSON(), nullable=False),
        sa.Column('decision_confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('human_override', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('resolved_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['orchestration_id'], ['orchestration_sessions.id']),
        sa.ForeignKeyConstraint(['task_id'], ['plan_tasks.id']),
        sa.ForeignKeyConstraint(['resolved_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('conflict_records')
    op.drop_table('review_outcomes')
    op.drop_table('orchestration_events')
    op.drop_table('approval_requests')
    op.drop_table('delegation_records')
    op.drop_table('context_versions')
    op.drop_table('shared_context_records')
    op.drop_table('agent_messages')
    op.drop_table('task_dependencies')
    op.drop_table('plan_tasks')
    op.drop_table('orchestration_sessions')
    op.drop_table('orchestration_plans')
    op.drop_table('provider_configs')
    op.drop_table('agent_capabilities')
    op.drop_table('capabilities')
    op.drop_table('agent_versions')

    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c['name'] for c in inspector.get_columns('agents')]

    with op.batch_alter_table('agents', schema=None) as batch_op:
        for col_name in [
            'budget_limits', 'allowed_data_scopes', 'allowed_tools',
            'requires_human_approval', 'max_delegation_depth', 'max_retries',
            'timeout_seconds', 'max_concurrent_tasks', 'priority',
            'fallback_model', 'role', 'display_name'
        ]:
            if col_name in columns:
                batch_op.drop_column(col_name)


