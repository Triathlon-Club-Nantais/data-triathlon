"""season goals (#1373)

Revision ID: 325c308cab2d
Revises: 2901789fc3c8
Create Date: 2026-10-17 16:57:04.352451
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '325c308cab2d'
down_revision: Union[str, None] = '2901789fc3c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('season_goals',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=8), nullable=False),
    sa.Column('event_type', sa.String(length=64), nullable=True),
    sa.Column('target', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_season_goals_user_id'), ['user_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_season_goals_user_id'))

    op.drop_table('season_goals')
