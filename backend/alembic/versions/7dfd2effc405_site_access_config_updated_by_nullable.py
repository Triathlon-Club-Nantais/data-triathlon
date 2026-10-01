"""site access config updated_by nullable

`set-site-code` (#929) pose le code d'accès hors ligne, sur une base qui n'a
encore aucun utilisateur : l'auteur devient facultatif. Le downgrade échoue
s'il reste une ligne sans auteur, ce qui est voulu.

Revision ID: 7dfd2effc405
Revises: 4d95313cbf07
Create Date: 2026-09-30 17:31:03.574775
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7dfd2effc405'
down_revision: Union[str, None] = '4d95313cbf07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table("site_access_config") as batch_op:
        batch_op.alter_column("updated_by_user_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("site_access_config") as batch_op:
        batch_op.alter_column("updated_by_user_id", existing_type=sa.Integer(), nullable=False)
