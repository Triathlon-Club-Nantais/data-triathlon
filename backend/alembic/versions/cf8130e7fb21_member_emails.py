"""member emails (#1334)

Revision ID: cf8130e7fb21
Revises: 38cb33b39849
Create Date: 2026-10-11 16:15:52.797515
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cf8130e7fb21'
down_revision: Union[str, None] = '38cb33b39849'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('member_emails',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('season', sa.Integer(), nullable=False),
    sa.Column('source', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email', 'season', name='uq_member_email_season')
    )
    with op.batch_alter_table('member_emails', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_member_emails_season'), ['season'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('member_emails', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_member_emails_season'))

    op.drop_table('member_emails')
