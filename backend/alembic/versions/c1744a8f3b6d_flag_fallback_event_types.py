"""flag fallback event types

Marque `fallback` les épreuves déjà typées par le repli triathlon du classifieur
(#1744) : nom sans sport nommé et aucune participation dont les temps stockés
portent à la fois `swim` et `bike`. Les lignes `manual` ne sont jamais touchées.
Le prédicat est lu dans le code vivant, pas figé : la reprise ne tourne qu'une fois.

Revision ID: c1744a8f3b6d
Revises: b1743c5d9e2f
Create Date: 2026-10-21 13:00:00.000000
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.scrapers.classify import is_fallback_type, names_a_sport


revision: str = 'c1744a8f3b6d'
down_revision: Union[str, None] = 'b1743c5d9e2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_courses = sa.table(
    "courses",
    sa.column("id", sa.Integer),
    sa.column("name", sa.String),
    sa.column("event_type", sa.String),
    sa.column("event_type_origin", sa.String),
)
_participations = sa.table(
    "participations",
    sa.column("course_id", sa.Integer),
    sa.column("splits", sa.JSON),
)


def _has_swim_and_bike(splits) -> bool:
    # SQLite rend une chaîne, PostgreSQL (psycopg) un dict ; NULL possible.
    if isinstance(splits, str):
        splits = json.loads(splits)
    return isinstance(splits, dict) and "swim" in splits and "bike" in splits


def upgrade() -> None:
    bind = op.get_bind()
    candidates = [
        row
        for row in bind.execute(
            sa.select(_courses.c.id, _courses.c.name, _courses.c.event_type).where(
                _courses.c.event_type_origin == "classified",
                sa.or_(
                    _courses.c.event_type == "triathlon",
                    _courses.c.event_type.like("triathlon-%"),
                ),
            )
        )
        if not names_a_sport(row.name)
    ]
    if not candidates:
        return
    corroborated = {
        row.course_id
        for row in bind.execute(
            sa.select(_participations.c.course_id, _participations.c.splits).where(
                _participations.c.course_id.in_([row.id for row in candidates])
            )
        )
        if _has_swim_and_bike(row.splits)
    }
    flagged = [
        row.id
        for row in candidates
        if is_fallback_type(
            row.event_type, row.name, has_swim_and_bike=row.id in corroborated
        )
    ]
    if flagged:
        bind.execute(
            sa.update(_courses)
            .where(_courses.c.id.in_(flagged))
            .values(event_type_origin="fallback")
        )


def downgrade() -> None:
    op.get_bind().execute(
        sa.update(_courses)
        .where(_courses.c.event_type_origin == "fallback")
        .values(event_type_origin="classified")
    )
