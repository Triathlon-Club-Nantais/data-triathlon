"""ignored athlete pairs

Les paires de fiches qu'un admin a jugées distinctes depuis la revue d'identité
(#908, epic #1146) : elles n'y reviennent plus. `ON DELETE CASCADE` des deux
côtés, la paire disparaissant avec l'une ou l'autre fiche.

Revision ID: e1f3a5c7b9d2
Revises: d8b2f4a6c1e3
Create Date: 2026-10-02 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e1f3a5c7b9d2'
down_revision: str | None = 'd8b2f4a6c1e3'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        'ignored_athlete_pairs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('athlete_id_low', sa.Integer(), nullable=False),
        sa.Column('athlete_id_high', sa.Integer(), nullable=False),
        sa.Column('ignored_by_user_id', sa.Integer(), nullable=False),
        sa.Column('ignored_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['athlete_id_low'], ['athletes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['athlete_id_high'], ['athletes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['ignored_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('athlete_id_low', 'athlete_id_high', name='uq_ignored_athlete_pair'),
    )
    op.create_index('ix_ignored_athlete_pairs_athlete_id_low', 'ignored_athlete_pairs', ['athlete_id_low'])
    op.create_index('ix_ignored_athlete_pairs_athlete_id_high', 'ignored_athlete_pairs', ['athlete_id_high'])


def downgrade() -> None:
    op.drop_index('ix_ignored_athlete_pairs_athlete_id_high', table_name='ignored_athlete_pairs')
    op.drop_index('ix_ignored_athlete_pairs_athlete_id_low', table_name='ignored_athlete_pairs')
    op.drop_table('ignored_athlete_pairs')
