"""index fonctionnel sur le club normalisé de participations (perf scope=club, #351)

Revision ID: e9cdbf3a4866
Revises: 9427c6c5e84a
Create Date: 2026-08-14 22:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.core.club import CLUB_NORMALIZED_INDEX_EXPRESSION

revision: str = "e9cdbf3a4866"
down_revision: str | None = "9427c6c5e84a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    # `/api/v1/courses/events?scope=club` (et quatre `.filter(tcn_clause(...))`
    # de `participation_repository.py`, même colonne) filtrent sur
    # `tcn_clause(Participation.club)` : huit fonctions SQL imbriquées
    # (`replace` x4 pour les blancs non-ASCII, `lower`, `trim`, `replace` x3
    # pour aplatir les espaces) qu'aucun index ne pouvait servir — mesuré
    # 15-20x plus lent que le même endpoint sans `scope=club` (876-1906 ms
    # contre 92-109 ms, sondage #328/#351). Deux autres appels de
    # `participation_repository.py` évaluent `tcn_clause` dans un
    # `func.sum(case(...))` sur un groupe déjà restreint : un index accélère
    # une sélection de lignes, pas un booléen agrégé sur des lignes déjà
    # choisies — ces deux-là ne bénéficient pas dans les mêmes proportions.
    #
    # `EXPLAIN QUERY PLAN` sur la base de dev SQLite (~20 300 participations),
    # requête réelle de `course_repository._filtered(club_only=True)` :
    #
    #   AVANT (sans index) :
    #     CO-ROUTINE anon_1
    #       SCAN courses USING INDEX ix_courses_name
    #       SEARCH participations USING INDEX ix_participations_course_id (course_id=?)
    #     SCAN anon_1
    #   → la jointure emprunte l'index sur `course_id`, mais `tcn_clause` reste
    #     évaluée sur chacune des ~20 300 lignes joignables : aucun index ne
    #     sert le prédicat lui-même, seulement le JOIN.
    #
    #   APRÈS (avec cet index) :
    #     CO-ROUTINE anon_1
    #       SEARCH participations USING INDEX ix_participations_club_normalized (<expr>=?)
    #       SEARCH courses USING INTEGER PRIMARY KEY (rowid=?)
    #       USE TEMP B-TREE FOR DISTINCT
    #     SCAN anon_1
    #   → la recherche part du filtre `club`, indexé, et ne remonte plus que
    #     les lignes déjà connues comme TCN.
    #
    # Vérification Postgres : faite en revue de code sur un conteneur Postgres 16
    # réel — `CREATE INDEX` accepte l'expression (immutabilité de `trim`/`replace`/
    # `lower` reconnue par Postgres), et le planificateur choisit un
    # `Bitmap Index Scan` dessus. Pas de branche `dialect.name` ici : l'expression
    # compile à l'identique sur les deux moteurs (`replace`/`lower`/`trim`
    # génériques, aucune fonction propriétaire) — à la différence de `pg_trgm` ou
    # `unaccent`, qui exigent une extension Postgres absente de SQLite. La
    # vérification n'est pas automatisée en CI (pas d'étage Postgres), donc à
    # rejouer manuellement si `_normalise_sql` change un jour.
    op.create_index(
        "ix_participations_club_normalized",
        "participations",
        [sa.text(CLUB_NORMALIZED_INDEX_EXPRESSION)],
    )


def downgrade() -> None:
    op.drop_index("ix_participations_club_normalized", table_name="participations")
