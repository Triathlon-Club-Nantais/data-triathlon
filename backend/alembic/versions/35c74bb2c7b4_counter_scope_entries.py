"""counter scope entries

Porte en base les deux ensembles qui bornent les compteurs (#95) : les
disciplines exclues et les libellés reconnus comme libellés du club. Ils
vivaient en dur dans `app/core/discipline.py` et `app/core/club.py`.

L'amorçage pose les douze valeurs qui étaient dans le code, **écrites en
littéral**. Elles ne sont pas importées depuis `app.core` à dessein : une
migration doit rester lisible telle quelle des années après, indépendamment de
ce que le code est devenu — et surtout elle ne doit pas se mettre à semer autre
chose le jour où une constante bouge. Le prix de ce choix est deux sources pour
la même valeur ; `tests/test_migrations.py` vérifie qu'elles ne divergent pas.

Aucun auteur sur ces lignes (`created_by_user_id IS NULL`) : elles ne viennent
de personne, et l'écran d'administration les présente comme « Configuration
initiale ».

Revision ID: 35c74bb2c7b4
Revises: 1df0635fc2fd
Create Date: 2026-08-26 16:21:06.378641
"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '35c74bb2c7b4'
down_revision: Union[str, None] = '1df0635fc2fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_NON_FEDERAL_DISCIPLINE = "non_federal_discipline"
_CLUB_LABEL = "tcn_club_label"

_AMORCAGE: tuple[tuple[str, str], ...] = (
    (_NON_FEDERAL_DISCIPLINE, "trail"),
    (_NON_FEDERAL_DISCIPLINE, "cyclisme"),
    (_NON_FEDERAL_DISCIPLINE, "cyclisme-route"),
    (_NON_FEDERAL_DISCIPLINE, "cyclisme-clm"),
    (_NON_FEDERAL_DISCIPLINE, "course-a-pied"),
    (_NON_FEDERAL_DISCIPLINE, "course-a-pied-5k"),
    (_NON_FEDERAL_DISCIPLINE, "course-a-pied-10k"),
    (_NON_FEDERAL_DISCIPLINE, "course-a-pied-semi"),
    (_NON_FEDERAL_DISCIPLINE, "course-a-pied-marathon"),
    (_CLUB_LABEL, "triathlon club nantais"),
    (_CLUB_LABEL, "tri club nantais"),
    (_CLUB_LABEL, "tcn"),
)


def upgrade() -> None:
    table = op.create_table('counter_scope_entries',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('value', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kind', 'value', name='uq_counter_scope_kind_value')
    )
    with op.batch_alter_table('counter_scope_entries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_counter_scope_entries_kind'), ['kind'], unique=False)

    maintenant = datetime.now(UTC).replace(tzinfo=None)
    op.bulk_insert(
        table,
        [
            {
                "kind": kind,
                "value": value,
                "created_at": maintenant,
                "created_by_user_id": None,
            }
            for kind, value in _AMORCAGE
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table('counter_scope_entries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_counter_scope_entries_kind'))

    op.drop_table('counter_scope_entries')
