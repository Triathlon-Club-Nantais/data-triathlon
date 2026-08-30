"""add season_validations table

Revision ID: 9bee59a008d5
Revises: 0412893aa2ac
Create Date: 2026-08-28 20:13:01.940834
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9bee59a008d5'
down_revision: Union[str, None] = '0412893aa2ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('season_validations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('athlete_id', sa.Integer(), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('validated_by_user_id', sa.Integer(), nullable=False),
    sa.Column('validated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ),
    sa.ForeignKeyConstraint(['validated_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('athlete_id', 'season', name='uq_season_validation_athlete_season'),
    )
    with op.batch_alter_table('season_validations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_season_validations_athlete_id'), ['athlete_id'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('season_validations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_season_validations_athlete_id'))

    op.drop_table('season_validations')
