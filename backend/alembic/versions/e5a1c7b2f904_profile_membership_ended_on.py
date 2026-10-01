"""profile membership ended on

`personal_profiles.membership_ended_on` (#1158) : fin d'adhésion saisie par un
encadrant. La purge de rétention supprime le profil à la fin de la saison qui
suit. Nulle sur l'existant : aucun profil n'est purgé tant qu'un encadrant n'a
pas renseigné de fin d'adhésion.

Revision ID: e5a1c7b2f904
Revises: d49e03833de6
Create Date: 2026-10-01 16:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5a1c7b2f904'
down_revision: Union[str, None] = 'd49e03833de6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table("personal_profiles") as batch_op:
        batch_op.add_column(sa.Column("membership_ended_on", sa.Date(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("personal_profiles") as batch_op:
        batch_op.drop_column("membership_ended_on")
