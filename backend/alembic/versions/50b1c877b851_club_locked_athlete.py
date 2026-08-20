"""club_locked athlete

Revision ID: 50b1c877b851
Revises: aeb0b98d1a51
Create Date: 2026-08-20 12:45:00.067658
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '50b1c877b851'
down_revision: Union[str, None] = 'aeb0b98d1a51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `sa.false()` et non `sa.text('0')` proposé par l'autogénération : sur
    # PostgreSQL, un `DEFAULT 0` sur une colonne booléenne est refusé au type.
    # Ni la chaîne `'false'`, que SQLite relit `True` (cf. is_pending_validation
    # dans app/models/participation.py).
    #
    # `op.add_column` et non `batch_alter_table` : sur SQLite le batch recopie la
    # table entière, et toute fiche existante doit sortir de cette migration
    # **non verrouillée** — le club des coureurs déjà en base n'a jamais été
    # corrigé à la main, il suit donc l'import comme avant (#439).
    op.add_column(
        "athletes",
        sa.Column("club_locked", sa.Boolean(), server_default=sa.false(), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("athletes", "club_locked")
