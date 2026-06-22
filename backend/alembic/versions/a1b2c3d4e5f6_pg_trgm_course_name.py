"""active pg_trgm + index trigram sur courses.name (recherche course fuzzy)

Revision ID: a1b2c3d4e5f6
Revises: 723259e01cdd
Create Date: 2026-06-15 23:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "723259e01cdd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Recherche tolérante aux fautes (Levenshtein/trigram) côté Postgres uniquement.
    # SQLite (dev) ignore : la recherche y reste un ILIKE sous-chaîne.
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_courses_name_trgm "
        "ON courses USING gin (name gin_trgm_ops)"
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    op.execute("DROP INDEX IF EXISTS ix_courses_name_trgm")
    # On laisse l'extension pg_trgm en place (peut servir ailleurs).
