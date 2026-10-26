"""create phase10 security governance tables

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2026-09-13 21:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h1i2j3k4l5m6'
down_revision = 'g1h2i3j4k5l6'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Create organizations table
    op.create_table(
        'organizations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('slug', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('max_members', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('max_workflows', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('max_agents', sa.Integer(), nullable=False, server_default='20'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id'),
        sa.UniqueConstraint('slug')
    )
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_organizations_owner_user_id'), ['owner_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_organizations_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_organizations_slug'), ['slug'], unique=True)

    # 2. Create organization_members table
    op.create_table(
        'organization_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('org_role', sa.String(length=32), nullable=False, server_default='member'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('joined_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_member')
    )
    with op.batch_alter_table('organization_members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_organization_members_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_organization_members_user_id'), ['user_id'], unique=False)

    # 3. Create workflow_policies table
    op.create_table(
        'workflow_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('workflow_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('max_duration_seconds', sa.Integer(), nullable=True, server_default='3600'),
        sa.Column('max_retry_count', sa.Integer(), nullable=True, server_default='3'),
        sa.Column('max_parallelism', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('token_budget', sa.Integer(), nullable=True, server_default='100000'),
        sa.Column('require_human_approval', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('allow_external_side_effects', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('allow_scheduled_execution', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('allow_automatic_execution', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('allowed_tools', sa.JSON(), nullable=True),
        sa.Column('denied_tools', sa.JSON(), nullable=True),
        sa.Column('allowed_agent_ids', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id')
    )
    with op.batch_alter_table('workflow_policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_policies_created_by_user_id'), ['created_by_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_policies_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_policies_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_policies_workflow_id'), ['workflow_id'], unique=False)

    # 4. Create tool_policies table
    op.create_table(
        'tool_policies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('tool_name', sa.String(length=128), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('created_by_user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('is_dangerous', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('require_approval', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('timeout_seconds', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('max_invocations_per_hour', sa.Integer(), nullable=True, server_default='1000'),
        sa.Column('allowed_domains', sa.JSON(), nullable=True),
        sa.Column('denied_patterns', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id')
    )
    with op.batch_alter_table('tool_policies', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tool_policies_created_by_user_id'), ['created_by_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tool_policies_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tool_policies_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_tool_policies_tool_name'), ['tool_name'], unique=False)

    # 5. Create encrypted_credentials table
    op.create_table(
        'encrypted_credentials',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('credential_type', sa.String(length=64), nullable=False, server_default='api_key'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('encrypted_value', sa.Text(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('owner_user_id', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['owner_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id')
    )
    with op.batch_alter_table('encrypted_credentials', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_encrypted_credentials_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_encrypted_credentials_owner_user_id'), ['owner_user_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_encrypted_credentials_public_id'), ['public_id'], unique=True)

    # 6. Create rate_limit_state table
    op.create_table(
        'rate_limit_state',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('endpoint', sa.String(length=128), nullable=False),
        sa.Column('request_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('window_start', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('rate_limit_state', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_rate_limit_state_endpoint'), ['endpoint'], unique=False)
        batch_op.create_index(batch_op.f('ix_rate_limit_state_key'), ['key'], unique=False)
        batch_op.create_index(batch_op.f('ix_rate_limit_state_window_start'), ['window_start'], unique=False)

    # 7. Add organization_id to workflows, agents, workflow_schedules, and audit_events
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_workflows_organization_id', 'organizations', ['organization_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_workflows_organization_id'), ['organization_id'], unique=False)

    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_agents_organization_id', 'organizations', ['organization_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_agents_organization_id'), ['organization_id'], unique=False)

    with op.batch_alter_table('workflow_schedules', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_workflow_schedules_organization_id', 'organizations', ['organization_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_workflow_schedules_organization_id'), ['organization_id'], unique=False)

    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.add_column(sa.Column('organization_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('correlation_id', sa.String(length=64), nullable=True))
        batch_op.create_foreign_key('fk_audit_events_organization_id', 'organizations', ['organization_id'], ['id'])
        batch_op.create_index(batch_op.f('ix_audit_events_organization_id'), ['organization_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_audit_events_correlation_id'), ['correlation_id'], unique=False)


def downgrade():
    with op.batch_alter_table('audit_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_audit_events_correlation_id'))
        batch_op.drop_index(batch_op.f('ix_audit_events_organization_id'))
        batch_op.drop_constraint('fk_audit_events_organization_id', type_='foreignkey')
        batch_op.drop_column('correlation_id')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('workflow_schedules', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workflow_schedules_organization_id'))
        batch_op.drop_constraint('fk_workflow_schedules_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('agents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_agents_organization_id'))
        batch_op.drop_constraint('fk_agents_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workflows_organization_id'))
        batch_op.drop_constraint('fk_workflows_organization_id', type_='foreignkey')
        batch_op.drop_column('organization_id')

    op.drop_table('rate_limit_state')
    op.drop_table('encrypted_credentials')
    op.drop_table('tool_policies')
    op.drop_table('workflow_policies')
    op.drop_table('organization_members')
    op.drop_table('organizations')
