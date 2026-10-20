"""result claim kind (#1739)

Revision ID: a7c41e92d3b8
Revises: 23e9124847d5
Create Date: 2026-10-20 09:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7c41e92d3b8'
down_revision: Union[str, None] = '23e9124847d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('result_claims', schema=None) as batch_op:
        batch_op.add_column(sa.Column('kind', sa.String(length=16), server_default='result', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('result_claims', schema=None) as batch_op:
        batch_op.drop_column('kind')
