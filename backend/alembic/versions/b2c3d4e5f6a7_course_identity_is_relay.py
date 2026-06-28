"""course identity includes is_relay

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op

revision: str = 'b2c3d4e5f6a7'
down_revision: str | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Recrée la contrainte d'unicité en y ajoutant `is_relay`.
    # batch_alter_table → recréation de table sur SQLite, ALTER sur Postgres.
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_course_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_course_identity',
            ['name', 'event_date', 'event_type', 'is_relay'],
        )


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_course_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_course_identity',
            ['name', 'event_date', 'event_type'],
        )
