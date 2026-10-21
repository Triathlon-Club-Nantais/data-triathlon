"""course event_type_origin

Revision ID: a1745e7c0b2d
Revises: c38bc1342485
Create Date: 2026-10-21 14:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1745e7c0b2d'
down_revision: Union[str, None] = 'c38bc1342485'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('event_type_origin', sa.String(), server_default='classified', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('event_type_origin')
