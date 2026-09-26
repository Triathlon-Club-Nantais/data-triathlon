"""retire l'index non unique redondant de user_sessions.token_hash (#1061)

Revision ID: 9f2e3d4c5b6a
Revises: 8e1d2c3b4a5f
Create Date: 2026-09-26 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = '9f2e3d4c5b6a'
down_revision: Union[str, None] = '8e1d2c3b4a5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `uq_user_session_token` indexe déjà la colonne.
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_user_sessions_token_hash'))


def downgrade() -> None:
    with op.batch_alter_table('user_sessions', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_user_sessions_token_hash'), ['token_hash'], unique=False)
