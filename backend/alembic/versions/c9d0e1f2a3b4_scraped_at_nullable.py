"""scraped_at nullable sur courses — purge totale des résultats (#384)

Revision ID: c9d0e1f2a3b4
Revises: 05094fea3bc2
Create Date: 2026-08-15 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c9d0e1f2a3b4"
down_revision: str | None = "05094fea3bc2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # La purge totale des résultats (#384) remet `scraped_at` à `NULL` sur
    # toute la base pour forcer un rescrape immédiat — `services/cache.is_fresh`
    # lit déjà `course.scraped_at is None` comme « jamais scrapée ». Sans cette
    # migration, l'`UPDATE` échouerait sur la contrainte `NOT NULL` en
    # PostgreSQL.
    #
    # `batch_alter_table` **n'est pas optionnel** : SQLite ne sait pas relâcher
    # un `NOT NULL` par `ALTER COLUMN`, il faut recréer la table (copie +
    # rename), ce que le batch fait pour ce seul dialecte — PostgreSQL reçoit
    # l'`ALTER` direct.
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.alter_column("scraped_at", existing_type=sa.DateTime(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("courses", schema=None) as batch_op:
        batch_op.alter_column("scraped_at", existing_type=sa.DateTime(), nullable=False)
