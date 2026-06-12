"""distance_km et reclassement event_type

Revision ID: e734b8c5c962
Revises: e4211f35a275
Create Date: 2026-06-11 20:39:42.245319
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.orm import Session

from app.services.reclassify import reclassify_existing

revision: str = "e734b8c5c962"
down_revision: str | None = "e4211f35a275"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Schéma : nouvelle colonne nullable.
    op.add_column("courses", sa.Column("distance_km", sa.Float(), nullable=True))
    # 2. Données : normalisation + raffinage + backfill km (sans réseau, idempotent).
    bind = op.get_bind()
    session = Session(bind=bind)
    reclassify_existing(session)
    session.commit()


def downgrade() -> None:
    op.drop_column("courses", "distance_km")
