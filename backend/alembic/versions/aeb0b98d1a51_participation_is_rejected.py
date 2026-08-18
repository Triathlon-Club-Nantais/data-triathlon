"""participation is rejected

Revision ID: aeb0b98d1a51
Revises: 194ac2494048
Create Date: 2026-08-18 11:33:57.002901
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION

revision: str = 'aeb0b98d1a51'
down_revision: Union[str, None] = '194ac2494048'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        # `sa.false()` et non la chaîne `'false'` : cf. is_pending_validation
        # dans app/models/participation.py — même piège SQLite.
        batch_op.add_column(sa.Column('is_rejected', sa.Boolean(), server_default=sa.false(), nullable=False))

    # `batch_alter_table` recrée la table entière sur SQLite (copie + rename) :
    # sa réflexion ne sait pas relire l'index fonctionnel
    # `ix_participations_club_normalized`, donc la copie ne l'emporte pas
    # (même correctif que la migration 05094fea3bc2).
    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )


def downgrade() -> None:
    with op.batch_alter_table('participations', schema=None) as batch_op:
        batch_op.drop_column('is_rejected')

    if op.get_bind().dialect.name == "sqlite":
        op.create_index(
            "ix_participations_club_normalized",
            "participations",
            [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
        )
