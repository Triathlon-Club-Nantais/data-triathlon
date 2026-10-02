"""athlete oppositions

`athlete_oppositions` (#334) : l'empreinte de l'identité d'un athlète qui s'est
opposé à la publication de ses résultats, ses dates et son auteur. Aucun nom.

Revision ID: f2b8d4e61a37
Revises: e5a1c7b2f904
Create Date: 2026-10-01 18:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2b8d4e61a37'
down_revision: Union[str, None] = 'e5a1c7b2f904'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        "athlete_oppositions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identity_hash", sa.String(length=64), nullable=False),
        sa.Column("requested_on", sa.Date(), nullable=False),
        sa.Column("applied_at", sa.DateTime(), nullable=False),
        sa.Column("applied_by_user_id", sa.Integer(), nullable=True),
        sa.Column("anonymised_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["applied_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_athlete_oppositions_identity_hash"), "athlete_oppositions", ["identity_hash"], unique=True
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_athlete_oppositions_identity_hash"), table_name="athlete_oppositions")
    op.drop_table("athlete_oppositions")
