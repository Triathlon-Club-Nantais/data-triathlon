"""users.last_seen_at (#1326)

Revision ID: a7d3c91e4b20
Revises: cf8130e7fb21
Create Date: 2026-10-12 14:30:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7d3c91e4b20'
down_revision: Union[str, None] = 'cf8130e7fb21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.add_column('users', sa.Column('last_seen_at', sa.DateTime(), nullable=True))
    # Meilleure activité connue : la dernière ouverture de session, sinon la création.
    op.execute(
        "UPDATE users SET last_seen_at = COALESCE("
        "(SELECT MAX(user_sessions.created_at) FROM user_sessions WHERE user_sessions.user_id = users.id), "
        "created_at, CURRENT_TIMESTAMP)"
    )
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('last_seen_at', existing_type=sa.DateTime(), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('last_seen_at')
