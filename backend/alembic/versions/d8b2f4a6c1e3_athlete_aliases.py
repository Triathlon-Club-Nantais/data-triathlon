"""athlete aliases

Table des variantes d'identité mémorisées par une fusion admin (#908, epic
#1146) : la graphie de la fiche absorbée, que l'import résout désormais comme
l'identité de la fiche conservée. Une variante n'appartient qu'à une fiche
(`uq_athlete_alias`) et disparaît avec elle (`ON DELETE CASCADE`).

Revision ID: d8b2f4a6c1e3
Revises: c3a9d1e7f520
Create Date: 2026-10-02 09:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd8b2f4a6c1e3'
down_revision: str | None = 'c3a9d1e7f520'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        'athlete_aliases',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('last_name_key', sa.String(), nullable=False),
        sa.Column('first_name_key', sa.String(), nullable=False),
        sa.Column('athlete_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('last_name_key', 'first_name_key', name='uq_athlete_alias'),
    )
    op.create_index('ix_athlete_aliases_athlete_id', 'athlete_aliases', ['athlete_id'])


def downgrade() -> None:
    op.drop_index('ix_athlete_aliases_athlete_id', table_name='athlete_aliases')
    op.drop_table('athlete_aliases')
