"""natation non federal discipline

Sème `natation` parmi les disciplines exclues des compteurs (#1743). Littéral,
comme `35c74bb2c7b4` : `tests/test_migrations.py` vérifie l'accord avec le code.

Revision ID: b1743c5d9e2f
Revises: a1745e7c0b2d
Create Date: 2026-10-21 12:00:00.000000
"""
from datetime import UTC, datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1743c5d9e2f'
down_revision: Union[str, None] = 'a1745e7c0b2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # Gardé : une ligne ajoutée à la main depuis l'administration ferait échouer l'unicité.
    op.get_bind().execute(
        sa.text(
            "INSERT INTO counter_scope_entries (kind, value, created_at, created_by_user_id) "
            "SELECT :kind, :value, :created_at, NULL "
            "WHERE NOT EXISTS (SELECT 1 FROM counter_scope_entries "
            "WHERE kind = :kind AND value = :value)"
        ),
        {
            "kind": "non_federal_discipline",
            "value": "natation",
            "created_at": datetime.now(UTC).replace(tzinfo=None),
        },
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM counter_scope_entries "
        "WHERE kind = 'non_federal_discipline' AND value = 'natation'"
    )
