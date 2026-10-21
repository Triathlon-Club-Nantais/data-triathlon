"""public page settings

Revision ID: a3a874392e03
Revises: c84cbf6533c4
Create Date: 2026-10-21 16:23:19.881228
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'a3a874392e03'
down_revision: Union[str, None] = 'c84cbf6533c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

def upgrade() -> None:
    op.create_table('public_page_settings',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('hide_best_times', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('hide_progression', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('hide_comparison', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('links', sa.JSON(), nullable=False),
    sa.Column('pinned_participation_id', sa.Integer(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['pinned_participation_id'], ['participations.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('user_id')
    )
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('public', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('season_goals', schema=None) as batch_op:
        batch_op.drop_column('public')

    op.drop_table('public_page_settings')
