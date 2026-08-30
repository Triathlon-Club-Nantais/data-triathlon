"""club aliases

Crée la table `club_aliases` pour le mécanisme de fusion de variantes de
libellés de club, généralisant à tout club ce qui était jusqu'à présent
spécifique au TCN (#215, #635). Chaque alias normalisé est rattaché à un nom
canonique affiché, avec son auteur et sa date de création.

Aucun amorçage : la table naît vide. Les alias sont créés exclusivement par
voie API/UI, jamais par migration.

Revision ID: f93f6bf40e66
Revises: 9bee59a008d5
Create Date: 2026-08-30 16:34:55.894977
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f93f6bf40e66'
down_revision: Union[str, None] = '9bee59a008d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('club_aliases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('canonical_name', sa.String(length=120), nullable=False),
    sa.Column('alias_normalized', sa.String(length=120), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('created_by_user_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('alias_normalized')
    )
    with op.batch_alter_table('club_aliases', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_club_aliases_canonical_name'), ['canonical_name'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('club_aliases', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_club_aliases_canonical_name'))

    op.drop_table('club_aliases')
