"""course identity includes is_relay

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-28 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
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
    # Garde-fou : l'ancienne contrainte ignore `is_relay`. Si une épreuve a
    # généré deux courses (solo + relais) partageant (name, event_date,
    # event_type), recréer la contrainte planterait avec une IntegrityError
    # opaque. On détecte ces doublons d'abord pour échouer avec un message clair.
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            'SELECT name, event_date, event_type, COUNT(*) AS n '
            'FROM courses '
            'GROUP BY name, event_date, event_type '
            'HAVING COUNT(*) > 1'
        )
    ).fetchall()
    if duplicates:
        details = ', '.join(
            f'{row.name!r} ({row.event_date}, {row.event_type}): {row.n} courses'
            for row in duplicates
        )
        raise RuntimeError(
            'Downgrade impossible : des courses partagent (name, event_date, '
            'event_type) et ne se distinguent que par is_relay. Fusionnez ou '
            f'supprimez ces doublons avant le downgrade. Concernées : {details}'
        )

    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_constraint('uq_course_identity', type_='unique')
        batch_op.create_unique_constraint(
            'uq_course_identity',
            ['name', 'event_date', 'event_type'],
        )
