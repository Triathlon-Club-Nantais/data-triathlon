"""backfill athlete current club from latest dated race

Avant #965, le club actuel d'une fiche suivait l'ordre de traitement des
imports, pas la date des épreuves : rejouer une vieille course ramenait le club
de l'époque (constaté en preview, des membres TCN passés au club d'un Run & Bike
de février 2025). L'import applique désormais la règle ; cette migration aligne
l'existant, qu'un rescrape ne corrigerait que pour les épreuves rescrapées.

La règle est celle de `athlete_repository.latest_club_dates` et `club_is_current`,
**figée ici** : le club de la participation validée à l'épreuve datée la plus
récente, la dernière importée en cas d'égalité de date (un import à date égale
l'emporte). Une fiche verrouillée par un humain (`club_locked`) n'est pas
touchée, ni une fiche sans aucune épreuve datée portant un club.

Downgrade sans effet : le club laissé par l'ordre d'import n'avait pas de sens.

Revision ID: 8a22b130deca
Revises: d49e03833de6
Create Date: 2026-10-01 13:23:56.286203
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '8a22b130deca'
down_revision: Union[str, None] = 'd49e03833de6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

# `NOT` plutôt qu'une comparaison à `false` : sous SQLite, un `server_default`
# booléen se stocke en texte `'false'`, que seul le contexte numérique lit à 0.
_LATEST_CLUBS = sa.text(
    """
    SELECT athlete_id, club FROM (
        SELECT p.athlete_id, p.club, a.club AS current_club,
               ROW_NUMBER() OVER (
                   PARTITION BY p.athlete_id ORDER BY c.event_date DESC, p.id DESC
               ) AS position
        FROM participations p
        JOIN courses c ON c.id = p.course_id
        JOIN athletes a ON a.id = p.athlete_id
        WHERE p.club IS NOT NULL AND TRIM(p.club) <> ''
          AND c.event_date IS NOT NULL
          AND NOT p.is_pending_validation
          AND NOT a.club_locked
    ) ranked
    WHERE position = 1 AND (current_club IS NULL OR current_club <> club)
    """
)


def upgrade() -> None:
    connexion = op.get_bind()
    changes = [
        {"athlete_id": athlete_id, "club": club}
        for athlete_id, club in connexion.execute(_LATEST_CLUBS)
    ]
    if changes:
        connexion.execute(
            sa.text("UPDATE athletes SET club = :club WHERE id = :athlete_id"), changes
        )


def downgrade() -> None:
    pass
