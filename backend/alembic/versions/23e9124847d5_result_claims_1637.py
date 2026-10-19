"""result claims (#1637)

Revision ID: 23e9124847d5
Revises: 325c308cab2d
Create Date: 2026-10-19 10:45:24.750687
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '23e9124847d5'
down_revision: Union[str, None] = '325c308cab2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('result_claims',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('participation_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['participation_id'], ['participations.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'participation_id', name='uq_result_claim_user_participation')
    )
    with op.batch_alter_table('result_claims', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_result_claims_participation_id'), ['participation_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_result_claims_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_result_claims_user_id'), ['user_id'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('result_claims', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_result_claims_user_id'))
        batch_op.drop_index(batch_op.f('ix_result_claims_status'))
        batch_op.drop_index(batch_op.f('ix_result_claims_participation_id'))

    op.drop_table('result_claims')
