"""create phase7 async jobs and schedules tables

Revision ID: e1f2a3b4c5d6
Revises: d1e2f3a4b5c6
Create Date: 2026-09-13 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e1f2a3b4c5d6'
down_revision = 'd1e2f3a4b5c6'
branch_labels = None
depends_on = None


def upgrade():
    # ### Create async_workflow_jobs table ###
    op.create_table(
        'async_workflow_jobs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('workflow_execution_id', sa.Integer(), nullable=True),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=False, server_default='workflow_execution'),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='QUEUED'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('queue_name', sa.String(length=50), nullable=False, server_default='default'),
        sa.Column('requested_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_retries', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('progress_percentage', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('current_node_id', sa.String(length=50), nullable=True),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('failure_category', sa.String(length=100), nullable=True),
        sa.Column('cancellation_reason', sa.Text(), nullable=True),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('correlation_id', sa.String(length=255), nullable=True),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('execution_metadata', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.ForeignKeyConstraint(['workflow_execution_id'], ['workflow_executions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('async_workflow_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_workflow_execution_id'), ['workflow_execution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_celery_task_id'), ['celery_task_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_idempotency_key'), ['idempotency_key'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_correlation_id'), ['correlation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_async_workflow_jobs_created_at'), ['created_at'], unique=False)

    # ### Create execution_attempts table ###
    op.create_table(
        'execution_attempts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('celery_task_id', sa.String(length=255), nullable=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('worker_id', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='STARTED'),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True),
        sa.Column('failure_category', sa.String(length=100), nullable=True),
        sa.Column('retry_reason', sa.Text(), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('recovery_status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['async_workflow_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('execution_attempts', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_execution_attempts_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_execution_attempts_job_id'), ['job_id'], unique=False)

    # ### Create workflow_schedules table ###
    op.create_table(
        'workflow_schedules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('schedule_type', sa.String(length=20), nullable=False, server_default='cron'),
        sa.Column('cron_expression', sa.String(length=100), nullable=True),
        sa.Column('interval_seconds', sa.Integer(), nullable=True),
        sa.Column('timezone', sa.String(length=50), nullable=False, server_default='UTC'),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('next_run_at', sa.DateTime(), nullable=True),
        sa.Column('last_run_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('misfire_policy', sa.String(length=30), nullable=False, server_default='fire_once'),
        sa.Column('input_data', sa.JSON(), nullable=False),
        sa.Column('idempotency_key', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('workflow_schedules', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_schedules_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_schedules_user_id'), ['user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_schedules_workflow_id'), ['workflow_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_schedules_next_run_at'), ['next_run_at'], unique=False)

    # ### Create worker_health table ###
    op.create_table(
        'worker_health',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('worker_id', sa.String(length=100), nullable=False),
        sa.Column('hostname', sa.String(length=100), nullable=False),
        sa.Column('queues', sa.JSON(), nullable=False),
        sa.Column('active_tasks_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('registered_tasks', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='online'),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=True, server_default='1.0.0'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('worker_health', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_worker_health_worker_id'), ['worker_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_worker_health_last_heartbeat_at'), ['last_heartbeat_at'], unique=False)


def downgrade():
    op.drop_table('worker_health')
    op.drop_table('workflow_schedules')
    op.drop_table('execution_attempts')
    op.drop_table('async_workflow_jobs')
