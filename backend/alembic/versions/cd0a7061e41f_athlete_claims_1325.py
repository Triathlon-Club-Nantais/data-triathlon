"""athlete claims (#1325)

Revision ID: cd0a7061e41f
Revises: a7d3c91e4b20
Create Date: 2026-10-17 13:40:15.244257
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'cd0a7061e41f'
down_revision: Union[str, None] = 'a7d3c91e4b20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table('athlete_claims',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('athlete_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('decided_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['athlete_id'], ['athletes.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', name='uq_athlete_claim_user')
    )
    with op.batch_alter_table('athlete_claims', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_athlete_claims_athlete_id'), ['athlete_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_athlete_claims_status'), ['status'], unique=False)



def downgrade() -> None:
    with op.batch_alter_table('athlete_claims', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_athlete_claims_status'))
        batch_op.drop_index(batch_op.f('ix_athlete_claims_athlete_id'))

    op.drop_table('athlete_claims')
