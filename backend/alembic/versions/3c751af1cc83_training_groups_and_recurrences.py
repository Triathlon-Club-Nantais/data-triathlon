"""training groups and recurrences (#1291)

Revision ID: 3c751af1cc83
Revises: b0a5ce5d2183
Create Date: 2026-10-10 16:45:59.843618
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c751af1cc83'
down_revision: Union[str, None] = 'b0a5ce5d2183'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

FK_SESSION_RECURRENCE = "fk_training_sessions_recurrence_id"


def upgrade() -> None:
    op.create_table('training_recurrences',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=True),
    sa.Column('location', sa.String(), nullable=True),
    sa.Column('session_type', sa.String(), nullable=True),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('training_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('organisation_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['organisation_id'], ['organisations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('organisation_id', 'name', name='uq_training_group_org_name')
    )
    with op.batch_alter_table('training_groups', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_groups_organisation_id'), ['organisation_id'], unique=False)

    op.create_table('training_recurrence_groups',
    sa.Column('recurrence_id', sa.Integer(), nullable=False),
    sa.Column('training_group_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['recurrence_id'], ['training_recurrences.id'], ),
    sa.ForeignKeyConstraint(['training_group_id'], ['training_groups.id'], ),
    sa.PrimaryKeyConstraint('recurrence_id', 'training_group_id')
    )
    op.create_table('training_session_groups',
    sa.Column('training_session_id', sa.Integer(), nullable=False),
    sa.Column('training_group_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['training_group_id'], ['training_groups.id'], ),
    sa.ForeignKeyConstraint(['training_session_id'], ['training_sessions.id'], ),
    sa.PrimaryKeyConstraint('training_session_id', 'training_group_id')
    )
    op.create_table('training_group_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('training_group_id', sa.Integer(), nullable=False),
    sa.Column('profile_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['profile_id'], ['personal_profiles.id'], ),
    sa.ForeignKeyConstraint(['training_group_id'], ['training_groups.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('training_group_id', 'profile_id', name='uq_training_group_member')
    )
    with op.batch_alter_table('training_group_members', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_training_group_members_profile_id'), ['profile_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_training_group_members_training_group_id'), ['training_group_id'], unique=False)

    # Toutes les inscriptions existantes viennent d'un ajout manuel.
    with op.batch_alter_table('training_participants', schema=None) as batch_op:
        batch_op.add_column(sa.Column('added_manually', sa.Boolean(), server_default=sa.true(), nullable=False))

    with op.batch_alter_table('training_sessions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('recurrence_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('detached', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.create_index(batch_op.f('ix_training_sessions_recurrence_id'), ['recurrence_id'], unique=False)
        batch_op.create_foreign_key(FK_SESSION_RECURRENCE, 'training_recurrences', ['recurrence_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('training_sessions', schema=None) as batch_op:
        batch_op.drop_constraint(FK_SESSION_RECURRENCE, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_training_sessions_recurrence_id'))
        batch_op.drop_column('detached')
        batch_op.drop_column('recurrence_id')

    with op.batch_alter_table('training_participants', schema=None) as batch_op:
        batch_op.drop_column('added_manually')

    with op.batch_alter_table('training_group_members', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_group_members_training_group_id'))
        batch_op.drop_index(batch_op.f('ix_training_group_members_profile_id'))

    op.drop_table('training_group_members')
    op.drop_table('training_session_groups')
    op.drop_table('training_recurrence_groups')
    with op.batch_alter_table('training_groups', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_training_groups_organisation_id'))

    op.drop_table('training_groups')
    op.drop_table('training_recurrences')
