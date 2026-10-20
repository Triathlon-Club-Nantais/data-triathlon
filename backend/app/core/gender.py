"""Genre d'un athlète : `M`, `F` ou vide (#936).

Chaque fournisseur publie sa graphie (`H`, `Homme`, `M ()`, `W`…) et chaque
compteur l'interprétait à sa façon : la composition du club affichait 12 hommes
en « Non renseigné », et le roster comptait des podiums de genre que le KPI et
la liste des podiums excluaient. Le genre est donc normalisé une fois, à
l'import, et le « podium de genre » a une seule définition, en Python et en SQL,
sur le patron `is_tcn` / `tcn_clause`.
"""
import re
from collections.abc import Sequence

from sqlalchemy import and_

from app.core.text import deaccent

GENDERS = ("M", "F")

_MEN = frozenset({"M", "H", "HOMME", "HOMMES", "MASCULIN", "MASCULINE", "MALE", "MEN", "MAN"})
_WOMEN = frozenset({"F", "W", "FEMME", "FEMMES", "FEMININ", "FEMININE", "FEMALE", "WOMEN", "WOMAN", "DAME", "DAMES"})
_NON_LETTERS = re.compile(r"[^A-Z]+")


def normalize_gender(raw: str | None) -> str:
    """`M`, `F`, ou `""` pour tout le reste (`X`, `Mixte`, codes numériques).

    Une valeur hors binaire ne devient pas une catégorie : sa prise en charge
    est un choix produit distinct (hors périmètre de #936).
    """
    letters = _NON_LETTERS.sub("", deaccent(raw or "").upper())
    if letters in _MEN:
        return "M"
    if letters in _WOMEN:
        return "F"
    return ""


def is_gender_podium(rank_gender: int | None, gender: str | None) -> bool:
    """Un podium de genre ne compte que pour un athlète `M` ou `F`."""
    return rank_gender is not None and 1 <= rank_gender <= 3 and gender in GENDERS


def gender_podium_clause(rank_gender_column, gender_column):
    """Forme SQL d'`is_gender_podium`, les colonnes passées par l'appelant."""
    return and_(rank_gender_column.between(1, 3), gender_column.in_(GENDERS))


def gender_places(ranked: Sequence[tuple[int, int | None]], *, complete: bool) -> tuple[dict[int, int], bool]:
    """Place par sexe de la population classée `(id, rank_gender)`, dans l'ordre d'affichage.

    Officielle (`rank_gender`) si toutes les lignes en portent un, sans doublon,
    et, sur un classement `complete`, sans place au delà de l'effectif : un sexe
    enregistré qui contredit le fournisseur reprend sinon le rang de l'autre sexe
    (#1730). Sur un classement partiel (club seul), les trous sont légitimes.
    Sinon recalculée par position. Règle unique de l'épreuve et du challenge.
    """
    ranks = [rank for _, rank in ranked]
    official = (
        bool(ranks)
        and None not in ranks
        and len(set(ranks)) == len(ranks)
        and not (complete and max(ranks) > len(ranks))
    )
    if official:
        return dict(ranked), True
    return {key: position for position, (key, _) in enumerate(ranked, start=1)}, False
