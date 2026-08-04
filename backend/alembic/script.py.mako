"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}

## Lignes `##` : commentaires Mako, jamais rendus dans la migration générée.
## Les quatre attributs ci-dessus sont le contrat du module avec Alembic, qui les
## lit par réflexion (`Script.__init__`) : aucun code ne les référence, et
## l'analyse statique les tient donc pour du code mort (CodeQL
## `py/unused-global-variable`). `__all__` les déclare publics, ce que la requête
## reconnaît explicitement. Les supprimer aurait été l'autre voie, écartée :
## `--branch-label` échoue bruyamment sans sa section, `--depends-on` non — il
## serait silencieusement perdu.
# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
