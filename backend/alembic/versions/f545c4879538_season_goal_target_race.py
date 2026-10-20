"""season goal target race

Revision ID: f545c4879538
Revises: 23e9124847d5
Create Date: 2026-10-20 15:42:41.341327
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f545c4879538'
down_revision: Union[str, None] = '23e9124847d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('course_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('race_name', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('race_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('major', sa.Boolean(), server_default=sa.false(), nullable=False))
        batch_op.alter_column('target',
               existing_type=sa.INTEGER(),
               nullable=True)
        batch_op.create_foreign_key('fk_season_goals_course_id', 'courses', ['course_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    # Les objectifs d'épreuve cible n'existent pas dans l'ancien schéma (et peuvent n'avoir aucune cible).
    op.execute("DELETE FROM season_goals WHERE kind = 'race' OR target IS NULL")
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.drop_constraint('fk_season_goals_course_id', type_='foreignkey')
        batch_op.alter_column('target',
               existing_type=sa.INTEGER(),
               nullable=False)
        batch_op.drop_column('major')
        batch_op.drop_column('race_date')
        batch_op.drop_column('race_name')
        batch_op.drop_column('course_id')
