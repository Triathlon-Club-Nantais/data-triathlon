"""challenges

Classements Challenge (#1008) : `challenges`, `challenge_courses` (liens vers N
épreuves) et `challenge_results`, hors de `participations` par construction.

Revision ID: c1a11e9e1008
Revises: e1f3a5c7b9d2
Create Date: 2026-10-02 18:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c1a11e9e1008'
down_revision: Union[str, None] = 'e1f3a5c7b9d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    op.create_table(
        "challenges",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column("scraped_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", "event_date", name="uq_challenge_identity"),
    )
    op.create_table(
        "challenge_courses",
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("challenge_id", "course_id"),
    )
    op.create_index("ix_challenge_courses_course_id", "challenge_courses", ["course_id"])
    op.create_table(
        "challenge_results",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("challenge_id", sa.Integer(), nullable=False),
        sa.Column("athlete_id", sa.Integer(), nullable=False),
        sa.Column("bib_number", sa.String(), nullable=True),
        sa.Column("rank_overall", sa.Integer(), nullable=True),
        sa.Column("rank_gender", sa.Integer(), nullable=True),
        sa.Column("rank_category", sa.Integer(), nullable=True),
        sa.Column("total_time", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("raw_data", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["challenge_id"], ["challenges.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["athlete_id"], ["athletes.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("challenge_id", "bib_number", name="uq_challenge_result_bib"),
    )
    op.create_index("ix_challenge_results_challenge_id", "challenge_results", ["challenge_id"])
    op.create_index("ix_challenge_results_athlete_id", "challenge_results", ["athlete_id"])


def downgrade() -> None:
    op.drop_table("challenge_results")
    op.drop_table("challenge_courses")
    op.drop_table("challenges")
