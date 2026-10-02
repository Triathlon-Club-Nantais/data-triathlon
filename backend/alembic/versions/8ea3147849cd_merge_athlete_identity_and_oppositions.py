"""merge athlete identity and oppositions

Revision ID: 8ea3147849cd
Revises: e1f3a5c7b9d2, f2b8d4e61a37
Create Date: 2026-10-02 15:36:01.447612
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8ea3147849cd'
down_revision: Union[str, None] = ('e1f3a5c7b9d2', 'f2b8d4e61a37')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
