"""course ranked by laps

`courses.ranked_by_laps` (#993) : épreuve classée au nombre de tours sur une durée
fixe, où le temps ne mesure pas la performance. Posé par l'import à chaque
passage ; les épreuves existantes naissent à `false` et se corrigent au prochain
rescrape (courses 157 et 158 en production, suivi dans #1009).

Revision ID: d49e03833de6
Revises: ccda2de245af
Create Date: 2026-09-30 18:46:19.646107
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd49e03833de6'
down_revision: Union[str, None] = 'ccda2de245af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.add_column(
            sa.Column("ranked_by_laps", sa.Boolean(), nullable=False, server_default=sa.false())
        )


def downgrade() -> None:
    with op.batch_alter_table("courses") as batch_op:
        batch_op.drop_column("ranked_by_laps")
