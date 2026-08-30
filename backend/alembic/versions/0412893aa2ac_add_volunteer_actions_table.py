"""add volunteer_actions table

Revision ID: 0412893aa2ac
Revises: 611d55721316
Create Date: 2026-08-28 20:04:49.786413
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0412893aa2ac'
down_revision: Union[str, None] = '611d55721316'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # Additive seulement (#709) — la dérive d'index détectée sur `courses`/
    # `participations` par l'autogénération (reflection Postgres, sans
    # rapport avec cette feature) a été retirée à la relecture manuelle.
    op.create_table('volunteer_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('athlete_id', sa.Integer(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('declared_by_user_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['declared_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('volunteer_actions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_volunteer_actions_athlete_id'), ['athlete_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_volunteer_actions_season'), ['season'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('volunteer_actions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_volunteer_actions_season'))
        batch_op.drop_index(batch_op.f('ix_volunteer_actions_athlete_id'))

    op.drop_table('volunteer_actions')
