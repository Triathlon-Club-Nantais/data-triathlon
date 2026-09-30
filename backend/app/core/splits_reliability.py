"""
Complétude des splits par fournisseur — **définition unique**.

Certains chronométreurs ne publient les temps intermédiaires que pour une
partie des finishers : Breizh Chrono ne récupère les splits fins que sur la
fiche individuelle des membres du club. T2Area en est sorti avec son nouveau
markup (#898), qui publie les splits de tous les participants sur la liste. Un classement par segment
calculé là-dessus comparerait l'athlète à une poignée de coureurs tout en se
présentant comme un classement complet — d'où l'exclusion.

La liste est une liste d'**exclusion**, pas une liste blanche : un fournisseur
nouvellement enregistré est éligible par défaut. Une liste blanche se périmerait
silencieusement à chaque scraper ajouté (statistiques absentes sans que
personne le remarque) là où l'exclusion échoue de façon visible.

Sa mise à jour accompagne toujours une évolution du scraper concerné, dans la
même PR : la fiabilité d'un fournisseur est une propriété de son scraper, pas
un réglage métier arbitrable depuis un panel d'administration.
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.course import Course

#: Fournisseurs dont les splits ne couvrent qu'une partie des finishers.
UNRELIABLE_SPLIT_PROVIDERS: frozenset[str] = frozenset({
    "breizhchrono",
})

#: Saisie manuelle : un résultat isolé, jamais un classement d'épreuve.
MANUAL_PROVIDER = "manuel"


def has_reliable_splits(provider: str | None) -> bool:
    """Vrai si ce fournisseur publie les splits de **tous** les finishers."""
    normalized = (provider or "").strip().lower()
    if not normalized or normalized == MANUAL_PROVIDER:
        return False
    return normalized not in UNRELIABLE_SPLIT_PROVIDERS


def is_stats_eligible(course: "Course") -> bool:
    """Éligibilité aux statistiques détaillées : propriété de la course, pas de la participation.

    Une épreuve classée au nombre de tours (#993) en sort : comparer son temps à
    celui des positions de référence n'a pas de sens.
    """
    if getattr(course, "ranked_by_laps", False):
        return False
    return has_reliable_splits(getattr(course, "provider", None))
