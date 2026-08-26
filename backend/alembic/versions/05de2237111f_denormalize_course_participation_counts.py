"""denormalize course participation counts (#623)

Revision ID: 05de2237111f
Revises: 1df0635fc2fd
Create Date: 2026-08-26 16:33:58.015313
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.club import tcn_clause
from app.core.validation import validated_clause

revision: str = '05de2237111f'
down_revision: str | None = '1df0635fc2fd'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.add_column(sa.Column('participation_count', sa.Integer(), server_default='0', nullable=False))
        batch_op.add_column(sa.Column('tcn_count', sa.Integer(), server_default='0', nullable=False))

    # Backfill de l'existant : contrairement à `1df0635fc2fd` (géocodage, qui
    # appelle Nominatim et laisse le remplissage à une commande CLI), ce calcul
    # est un pur agrégat SQL sur des données déjà en base — rien n'empêche de
    # le faire ici, dans la même transaction que l'ajout des colonnes. Deux
    # sous-requêtes corrélées, portables SQLite/PostgreSQL (pas d'`UPDATE...
    # FROM`), sur la même définition que `_apply_filters`/`tcn_clause` de
    # `participation_repository.py` : `validated_clause` (une participation en
    # attente ne compte dans aucun agrégat public, #270) et `tcn_clause` sur
    # `Participation.club` (jamais `Athlete.club`).
    courses = sa.table(
        "courses",
        sa.column("id"),
        sa.column("participation_count"),
        sa.column("tcn_count"),
    )
    participations = sa.table(
        "participations",
        sa.column("id"),
        sa.column("course_id"),
        sa.column("is_pending_validation"),
        sa.column("club"),
    )
    comptees = sa.select(sa.func.count(participations.c.id)).where(
        participations.c.course_id == courses.c.id,
        validated_clause(participations.c.is_pending_validation),
    )
    op.execute(
        courses.update().values(
            participation_count=comptees.scalar_subquery(),
            tcn_count=comptees.where(tcn_clause(participations.c.club)).scalar_subquery(),
        )
    )


def downgrade() -> None:
    with op.batch_alter_table('courses', schema=None) as batch_op:
        batch_op.drop_column('tcn_count')
        batch_op.drop_column('participation_count')
