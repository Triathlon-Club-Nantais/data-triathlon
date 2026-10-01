"""normalize athlete gender

`athletes.gender` recopiait la graphie de chaque fournisseur (`H`, `Homme`,
`F ()`, `X`…) : la composition du club affichait des hommes en « Non
renseigné » (#936). L'import normalise désormais en `M`, `F` ou vide ; cette
migration aligne l'existant.

La règle est **figée ici** plutôt qu'importée de `app.core.gender` : une
migration rejouée plus tard doit produire le même résultat, même si le code
applicatif évolue. Chaque valeur distincte est lue, normalisée en Python, puis
réécrite par un `UPDATE` ciblé : aucune dépendance à `unaccent` ni aux
fonctions de chaîne de l'un ou l'autre moteur.

Downgrade sans effet : la graphie d'origine n'est pas conservée, et rien ne
dépend d'elle.

Revision ID: ccda2de245af
Revises: 7dfd2effc405
Create Date: 2026-09-30 18:40:12.000000
"""
import re
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'ccda2de245af'
down_revision: Union[str, None] = '7dfd2effc405'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Contrat lu par réflexion par Alembic (cf. `script.py.mako`), jamais référencé ici.
__all__ = ["revision", "down_revision", "branch_labels", "depends_on", "upgrade", "downgrade"]

_MEN = frozenset({"M", "H", "HOMME", "HOMMES", "MASCULIN", "MASCULINE", "MALE", "MEN", "MAN"})
_WOMEN = frozenset({"F", "W", "FEMME", "FEMMES", "FEMININ", "FEMININE", "FEMALE", "WOMEN", "WOMAN", "DAME", "DAMES"})


def _normalize(raw: str | None) -> str:
    decomposed = unicodedata.normalize("NFKD", raw or "")
    letters = re.sub(r"[^A-Z]+", "", "".join(c for c in decomposed if not unicodedata.combining(c)).upper())
    if letters in _MEN:
        return "M"
    if letters in _WOMEN:
        return "F"
    return ""


def upgrade() -> None:
    connexion = op.get_bind()
    valeurs = connexion.execute(sa.text("SELECT DISTINCT gender FROM athletes")).scalars().all()
    for valeur in valeurs:
        cible = _normalize(valeur)
        if valeur == cible:
            continue
        if valeur is None:
            connexion.execute(sa.text("UPDATE athletes SET gender = :cible WHERE gender IS NULL"), {"cible": cible})
        else:
            connexion.execute(
                sa.text("UPDATE athletes SET gender = :cible WHERE gender = :valeur"),
                {"cible": cible, "valeur": valeur},
            )


def downgrade() -> None:
    pass
