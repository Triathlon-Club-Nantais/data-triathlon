"""indexe l'identité d'athlète en minuscules (#1005)

Revision ID: daf0d7d41178
Revises: a1c2e3f4b5d6
Create Date: 2026-09-28 12:40:31.172997
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'daf0d7d41178'
down_revision: Union[str, None] = 'a1c2e3f4b5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `get_by_identities_batch` filtre sur `(lower(nom), lower(prenom))` : sans cet
    # index, chaque lot parcourait toute la table (2 636 s mesurées sur la preview).
    op.create_index(
        'ix_athletes_identity',
        'athletes',
        [sa.text('lower(nom)'), sa.text('lower(prenom)')],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_athletes_identity', table_name='athletes')
