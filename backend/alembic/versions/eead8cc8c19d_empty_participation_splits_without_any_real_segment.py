"""empty participation splits without any real segment

Les aquathlons Sport Innovation de Carnac (#1194) portaient `{"swim": "FRA"}` :
la nationalité lue comme la natation. L'import écarte depuis #971 tout segment
qui n'est pas une durée positive, mais « vide n'écrase pas » : un rescrape qui
n'écrit plus aucun segment laisse la ligne en l'état. Cette migration vide
(`NULL`, ce qu'écrit l'import) toute ligne dont **aucun** segment n'est une
durée positive, ce qui couvre aussi le mélange zéros et « FRA » laissé par
`50f5db3c0a88`.

Une ligne qui garde un segment réel est réécrite par son prochain rescrape,
l'import y écartant l'illisible. La lecture d'une durée est **figée ici**
(celle de `mapping.parse_duration`) pour que la migration rejouée plus tard
produise le même résultat.

Downgrade sans effet : ces valeurs ne portaient aucune durée.

Revision ID: eead8cc8c19d
Revises: c1a11e9e1008
Create Date: 2026-10-06 13:50:00.000000
"""
import json
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'eead8cc8c19d'
down_revision: Union[str, None] = 'c1a11e9e1008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_DURATION = re.compile(r"(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})")


def _positive_duration(value) -> bool:
    if not isinstance(value, str):
        return False
    match = _DURATION.fullmatch(value.strip())
    if not match or int(match["minutes"]) >= 60 or int(match["seconds"]) >= 60:
        return False
    return int(match["hours"] or 0) * 3600 + int(match["minutes"]) * 60 + int(match["seconds"]) > 0


def _without_real_segment(splits) -> bool:
    if isinstance(splits, str):
        splits = json.loads(splits)
    return bool(splits) and not any(_positive_duration(value) for value in splits.values())


def upgrade() -> None:
    connexion = op.get_bind()
    candidates = connexion.execute(
        sa.text("SELECT id, splits FROM participations WHERE splits IS NOT NULL")
    )
    emptied = [{"id": row_id} for row_id, splits in candidates if _without_real_segment(splits)]
    if emptied:
        connexion.execute(sa.text("UPDATE participations SET splits = NULL WHERE id = :id"), emptied)


def downgrade() -> None:
    pass
