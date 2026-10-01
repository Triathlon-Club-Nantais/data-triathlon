"""empty participation splits made only of zero segments

`00:00:00` est un point de passage non franchi (Klikego, Breizh Chrono) :
l'import l'écarte depuis #971. Mais « vide n'écrase pas » : un rescrape ne vide
pas une ligne dont **tous** les segments sont écartés, et ces lignes gardaient
des splits faits de zéros. Cette migration les vide (`NULL`, ce qu'écrit
l'import quand aucun segment ne reste), quel que soit le statut, comme l'import.

Seul le cas « tous les segments valent zéro » est traité : une ligne qui garde
un segment réel est réécrite par son prochain rescrape. Reste hors périmètre une
ligne mêlant zéros et valeurs illisibles (« FRA ») : l'import les écarterait
tous, et « vide n'écrase pas » la laisse en l'état. La lecture d'une durée
est **figée ici** (celle de `mapping.parse_duration`) pour que la migration
rejouée plus tard produise le même résultat.

Downgrade sans effet : des zéros ne portaient aucune information.

Revision ID: 50f5db3c0a88
Revises: 8a22b130deca
Create Date: 2026-10-01 13:25:44.882575
"""
import json
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '50f5db3c0a88'
down_revision: Union[str, None] = '8a22b130deca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_ZERO_DURATION = re.compile(r"(?:0+:)?0{1,2}:00")


def _only_zero_segments(splits) -> bool:
    if isinstance(splits, str):
        splits = json.loads(splits)
    return bool(splits) and all(
        isinstance(value, str) and _ZERO_DURATION.fullmatch(value.strip())
        for value in splits.values()
    )


def upgrade() -> None:
    connexion = op.get_bind()
    candidates = connexion.execute(
        sa.text(
            "SELECT id, splits FROM participations"
            " WHERE splits IS NOT NULL AND CAST(splits AS TEXT) LIKE '%0:00%'"
        )
    )
    emptied = [{"id": row_id} for row_id, splits in candidates if _only_zero_segments(splits)]
    if emptied:
        connexion.execute(sa.text("UPDATE participations SET splits = NULL WHERE id = :id"), emptied)


def downgrade() -> None:
    pass
