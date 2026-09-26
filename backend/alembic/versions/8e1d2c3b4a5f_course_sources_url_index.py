"""index partiel sur course_sources.url des sources actives (#1025)

Revision ID: 8e1d2c3b4a5f
Revises: c10f3d7ae85e
Create Date: 2026-09-26 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8e1d2c3b4a5f'
down_revision: Union[str, None] = 'c10f3d7ae85e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # Hors `batch_alter_table`, pour que les arguments de dialecte soient
    # relayés (même précaution que `a2b3c4d5e6f7_course_sources.py`).
    op.create_index(
        'ix_course_sources_url_active',
        'course_sources',
        ['url'],
        unique=False,
        sqlite_where=sa.text('is_active = 1'),
        postgresql_where=sa.text('is_active'),
    )


def downgrade() -> None:
    op.drop_index('ix_course_sources_url_active', table_name='course_sources')
