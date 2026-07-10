"""indice de fiabilité des données d'une course

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-10 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable sans valeur par défaut : les courses déjà en base n'ont jamais été
    # évaluées, et NULL le dit — contrairement à un `false` qui les déclarerait
    # toutes suspectes, ou à un `true` qui les blanchirait sans preuve.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_reliable', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('quality_issues', sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('quality_issues')
        batch_op.drop_column('is_reliable')
