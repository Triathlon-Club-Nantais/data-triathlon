"""benevole access config table — mot de passe géré en base plutôt qu'en env (#271)

Revision ID: 194ac2494048
Revises: 595676d81c48
Create Date: 2026-08-15 23:10:52.328349

Aucune reprise de données : `BENEVOLE_SHARED_PASSWORD` était un mot de passe
en clair, non haché — il n'y a rien à migrer vers `password_hash`/
`password_salt` sans le connaître, et un administrateur doit de toute façon
en définir un neuf depuis le back-office (`specs/20260815-173645-admin-mdp-
benevoles/quickstart.md`, scénario 1).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '194ac2494048'
down_revision: Union[str, None] = '595676d81c48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        "benevole_access_config",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("password_salt", sa.String(), nullable=False),
        sa.Column("session_secret", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by_user_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("benevole_access_config")
