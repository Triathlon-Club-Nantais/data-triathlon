"""team label identity keys

Un libellé d'équipe « ARNAUD & VINCENT » prenait la clé `arnaud|vincent` de la
personne « ARNAUD Vincent » (#1192) : la reprise des doublons (#906) a fusionné
deux résultats d'équipe dans des personnes. Depuis, `athlete_identity_keys`
garde le séparateur (`arnaud&vincent`), et cette migration recalcule les fiches
existantes dont le nom porte `&`, `/` ou `+` bordé d'une espace, ou « et » en
mot entier, et la clé source (`<nom>|<prénom>`, #896) de leurs résultats : sans
elle, le rescrape suivant ne reconnaîtrait plus ces lignes. Deux
graphies d'une même équipe tombent alors sur la même clé : la plus ancienne
reste principale, les suivantes prennent les rangs d'homonyme libres.

La règle est **figée ici** pour que la migration rejouée plus tard produise le
même résultat. Downgrade sans effet : l'ancienne clé était fausse.

Revision ID: baef0d35bb4f
Revises: eead8cc8c19d
Create Date: 2026-10-06 15:30:00.000000
"""
import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'baef0d35bb4f'
down_revision: Union[str, None] = 'eead8cc8c19d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_LIGATURES = str.maketrans({"œ": "oe", "æ": "ae", "ø": "o", "ł": "l", "đ": "d"})
_TEAM_SEPARATOR = re.compile(r"(?:^|\s)[&/+]|[&/+](?:\s|$)|\bet\b", re.IGNORECASE)


def _identity_key(text: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()
    return "".join(c for c in folded.translate(_LIGATURES) if c.isalnum())


def _team_key(nom: str | None, prenom: str | None) -> str | None:
    parts = [_identity_key(part) for part in _TEAM_SEPARATOR.split(f"{nom or ''} {prenom or ''}")]
    parts = [part for part in parts if part]
    return "&".join(parts) if len(parts) > 1 else None


def upgrade() -> None:
    connexion = op.get_bind()
    rows = connexion.execute(
        sa.text("SELECT id, nom, prenom, last_name_key, first_name_key FROM athletes ORDER BY id")
    ).all()
    teams = [
        (row_id, key, f"{old_last}|{old_first}")
        for row_id, nom, prenom, old_last, old_first in rows
        if (key := _team_key(nom, prenom))
    ]
    if not teams:
        return
    taken: dict[str, set[int]] = {}
    for key, rank in connexion.execute(
        sa.text("SELECT last_name_key, homonym_rank FROM athletes WHERE first_name_key = ''")
    ):
        taken.setdefault(key, set()).add(rank)
    for row_id, key, old_source_key in teams:
        rank = 0
        while rank in taken.get(key, set()):
            rank += 1
        taken.setdefault(key, set()).add(rank)
        connexion.execute(
            sa.text(
                "UPDATE athletes SET last_name_key = :key, first_name_key = '', homonym_rank = :rank"
                " WHERE id = :id"
            ),
            {"key": key, "rank": rank, "id": row_id},
        )
        connexion.execute(
            sa.text(
                "UPDATE participations SET source_identity_key = :new"
                " WHERE athlete_id = :id AND source_identity_key = :old"
            ),
            {"new": f"{key}|", "old": old_source_key, "id": row_id},
        )


def downgrade() -> None:
    pass
