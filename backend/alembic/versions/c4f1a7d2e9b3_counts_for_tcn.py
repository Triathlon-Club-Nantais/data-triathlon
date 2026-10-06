"""counts_for_tcn and ambiguous club labels (#1206)

Un libellé « TCN » seul est aussi celui du Triathlon Club Narbonne : la portée
gagne un drapeau `ambiguous`, posé ici sur `tcn`, et chaque résultat porte son
verdict dans `participations.counts_for_tcn`. Le backfill applique la règle en
SQL, écrite ici (seule la normalisation du libellé est importée de
`core/club`) : un libellé non ambigu de la portée compte ; un libellé
ambigu compte si l'athlète a un autre résultat validé sous un libellé non
ambigu. Puis `courses.tcn_count` est recalculé depuis la colonne.

Revision ID: c4f1a7d2e9b3
Revises: baef0d35bb4f
Create Date: 2026-10-06 18:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION, _normalise_sql

revision: str = 'c4f1a7d2e9b3'
down_revision: Union[str, None] = 'baef0d35bb4f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `op.add_column` et non `batch_alter_table` : sur SQLite, le batch recrée la
    # table et perd l'index fonctionnel du club (cf. `05094fea3bc2`).
    op.add_column(
        'counter_scope_entries',
        sa.Column('ambiguous', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        'participations',
        sa.Column('counts_for_tcn', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.create_index('ix_participations_counts_for_tcn', 'participations', ['counts_for_tcn'])

    entries = sa.table(
        'counter_scope_entries', sa.column('kind'), sa.column('value'), sa.column('ambiguous')
    )
    op.execute(
        entries.update()
        .where(entries.c.kind == 'tcn_club_label', entries.c.value == 'tcn')
        .values(ambiguous=True)
    )

    connexion = op.get_bind()
    rows = connexion.execute(
        sa.select(entries.c.value, entries.c.ambiguous).where(entries.c.kind == 'tcn_club_label')
    ).all()
    clear = sorted(value for value, ambiguous in rows if not ambiguous)
    ambiguous = sorted(value for value, ambiguous in rows if ambiguous)

    p = sa.table(
        'participations',
        sa.column('id'), sa.column('athlete_id'), sa.column('course_id'), sa.column('club'),
        sa.column('is_pending_validation'), sa.column('counts_for_tcn'),
    )
    other = p.alias('other')
    attached = (
        sa.select(sa.literal(1))
        .select_from(other)
        .where(
            other.c.athlete_id == p.c.athlete_id,
            other.c.id != p.c.id,
            other.c.is_pending_validation.is_(False),
            _normalise_sql(other.c.club).in_(clear),
        )
        .exists()
    )
    rule = sa.or_(
        _normalise_sql(p.c.club).in_(clear),
        sa.and_(_normalise_sql(p.c.club).in_(ambiguous), attached),
    )
    op.execute(p.update().values(counts_for_tcn=sa.case((rule, True), else_=False)))

    courses = sa.table('courses', sa.column('id'), sa.column('tcn_count'))
    counted = (
        sa.select(sa.func.count(p.c.id))
        .where(
            p.c.course_id == courses.c.id,
            p.c.is_pending_validation.is_(False),
            p.c.counts_for_tcn.is_(True),
        )
        .scalar_subquery()
    )
    op.execute(courses.update().values(tcn_count=counted))


def downgrade() -> None:
    op.drop_index('ix_participations_counts_for_tcn', table_name='participations')
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.drop_column('counts_for_tcn')
    with op.batch_alter_table('counter_scope_entries', schema=None) as batch_op:
        batch_op.drop_column('ambiguous')
    # Le batch SQLite a recréé `participations` sans l'index fonctionnel.
    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )
