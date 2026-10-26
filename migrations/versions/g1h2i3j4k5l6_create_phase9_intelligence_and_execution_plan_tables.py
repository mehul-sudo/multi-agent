"""create phase9 intelligence and execution plan tables

Revision ID: g1h2i3j4k5l6
Revises: f2a3b4c5d6e7
Create Date: 2026-09-13 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2i3j4k5l6'
down_revision = 'f2a3b4c5d6e7'
branch_labels = None
depends_on = None


def upgrade():
    # ### Alter workflows table for priority ###
    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.add_column(sa.Column('priority', sa.Integer(), nullable=False, server_default='1'))

    # ### Alter workflow_dependencies table for is_optional and condition ###
    with op.batch_alter_table('workflow_dependencies', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_optional', sa.Boolean(), nullable=False, server_default=sa.text('0')))
        batch_op.add_column(sa.Column('condition', sa.Text(), nullable=True))

    # ### Create workflow_execution_plans table ###
    op.create_table(
        'workflow_execution_plans',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('public_id', sa.String(length=36), nullable=False),
        sa.Column('workflow_id', sa.Integer(), nullable=False),
        sa.Column('execution_id', sa.Integer(), nullable=True),
        sa.Column('stages', sa.JSON(), nullable=False),
        sa.Column('node_priorities', sa.JSON(), nullable=False),
        sa.Column('dependency_rules', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='created'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('public_id')
    )
    with op.batch_alter_table('workflow_execution_plans', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_workflow_execution_plans_execution_id'), ['execution_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_workflow_execution_plans_public_id'), ['public_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_workflow_execution_plans_workflow_id'), ['workflow_id'], unique=False)


def downgrade():
    with op.batch_alter_table('workflow_execution_plans', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_workflow_execution_plans_workflow_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_execution_plans_public_id'))
        batch_op.drop_index(batch_op.f('ix_workflow_execution_plans_execution_id'))
    op.drop_table('workflow_execution_plans')

    with op.batch_alter_table('workflow_dependencies', schema=None) as batch_op:
        batch_op.drop_column('condition')
        batch_op.drop_column('is_optional')

    with op.batch_alter_table('workflows', schema=None) as batch_op:
        batch_op.drop_column('priority')
