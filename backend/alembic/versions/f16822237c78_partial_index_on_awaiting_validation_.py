"""index partiel sur les résultats en attente de validation (#1390)

Revision ID: f16822237c78
Revises: 3c751af1cc83
Create Date: 2026-10-15 18:49:21.996962
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f16822237c78'
down_revision: Union[str, None] = '3c751af1cc83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # Hors `batch_alter_table`, pour que les arguments de dialecte soient
    # relayés (même précaution que `8e1d2c3b4a5f_course_sources_url_index.py`).
    op.create_index(
        'ix_participations_awaiting_validation',
        'participations',
        ['course_id'],
        unique=False,
        postgresql_where=sa.text('is_pending_validation IS true AND is_rejected IS false'),
        sqlite_where=sa.text('is_pending_validation IS 1 AND is_rejected IS 0'),
    )


def downgrade() -> None:
    op.drop_index('ix_participations_awaiting_validation', table_name='participations')
