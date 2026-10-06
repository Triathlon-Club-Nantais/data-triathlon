"""athlete known clubs

Clubs confirmés par un admin pour une fiche (#1209), et auteur facultatif d'une
paire ignorée, que l'import pose désormais sans humain.

Revision ID: f3a8c1d7b6e4
Revises: d2b6e8a1c5f3
Create Date: 2026-10-06 20:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a8c1d7b6e4'
down_revision: Union[str, None] = 'd2b6e8a1c5f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        "athlete_known_clubs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("athlete_id", sa.Integer(), sa.ForeignKey("athletes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("club_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("athlete_id", "club_key", name="uq_athlete_known_club"),
    )
    op.create_index("ix_athlete_known_clubs_athlete_id", "athlete_known_clubs", ["athlete_id"])
    with op.batch_alter_table("ignored_athlete_pairs") as batch:
        batch.alter_column("ignored_by_user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.execute("DELETE FROM ignored_athlete_pairs WHERE ignored_by_user_id IS NULL")
    with op.batch_alter_table("ignored_athlete_pairs") as batch:
        batch.alter_column("ignored_by_user_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_athlete_known_clubs_athlete_id", table_name="athlete_known_clubs")
    op.drop_table("athlete_known_clubs")
