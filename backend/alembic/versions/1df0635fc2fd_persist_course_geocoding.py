"""persist course geocoding

Revision ID: 1df0635fc2fd
Revises: 50b1c877b851
Create Date: 2026-08-25 18:35:16.085503
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '1df0635fc2fd'
down_revision: str | None = '50b1c877b851'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # Colonnes vides : cette migration ne géocode rien (#579). Le remplissage
    # est le rôle de `python -m app.cli geocode-courses`, à lancer une fois sur
    # l'existant après le déploiement — un remplissage synchrone dans la
    # migration referait, sous une autre forme, le défaut que #579 corrige.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('geocoded_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('geocoded_at')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
