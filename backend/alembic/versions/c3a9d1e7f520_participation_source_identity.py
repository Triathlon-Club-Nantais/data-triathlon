"""participation source identity

Chaque résultat retient la clé d'identité de la ligne source qui l'a produit
(`source_identity_key`, `<nom>|<prénom>` normalisés, #907), et un drapeau posé
par une réattribution admin (`athlete_locked`). Un rescrape apparie alors une
ligne sans dossard par cette clé, et non plus par sa fiche, et ne défait plus
une correction admin (#896, epic #1146).

Rétro-remplissage : la clé de la fiche actuelle, en une requête. Juste pour
tout résultat jamais réattribué ; une réattribution passée, déjà défaite ou non,
est hors périmètre (spec #1146).

Revision ID: c3a9d1e7f520
Revises: b7e41c9d2a58
Create Date: 2026-10-01 18:30:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3a9d1e7f520'
down_revision: str | None = 'b7e41c9d2a58'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_identity_key', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('athlete_locked', sa.Boolean(), server_default=sa.false(), nullable=False))
    op.execute(
        "UPDATE participations SET source_identity_key = ("
        " SELECT athletes.last_name_key || '|' || athletes.first_name_key"
        " FROM athletes WHERE athletes.id = participations.athlete_id)"
    )


def downgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.drop_column('athlete_locked')
        batch_op.drop_column('source_identity_key')
