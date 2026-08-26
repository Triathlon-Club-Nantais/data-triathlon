"""
Portée des compteurs — les deux ensembles, en mémoire de processus (#95).

Ce que l'application compte tient à deux listes : les disciplines exclues des
compteurs, et les libellés reconnus comme libellés du club. Elles vivaient en
dur dans `core/discipline.py` et `core/club.py` ; elles vivent désormais en
base, éditables depuis le panel admin.

**Les prédicats gardent la règle, ce module porte les données.** `is_tcn`,
`is_federal` et leurs miroirs SQL lisent ici. Personne d'autre.

**Aucune Session, aucun import d'une couche supérieure** — c'est ce qui autorise
ce module dans `core/` (Principe II). Le registre est **rempli depuis le
dessus** : `services/counter_scope.load_from_db` lit la base et pousse le
résultat ici. Trois points de remplissage, et trois seulement — le démarrage de
l'API, l'entrée de la CLI, et chaque écriture d'administration. Un chargement
paresseux depuis la base était exclu : `ParticipationOut.is_tcn` est un champ
calculé de DTO, évalué sans Session et sans personne pour lui en passer une.

**Les défauts sont les valeurs d'avant la bascule**, et ce n'est pas un repli de
confort : un registre vide rendrait zéro résultat du club, donc tous les
compteurs du club à zéro, sans erreur ni avertissement — un tableau de bord vide
qui ressemble à un tableau de bord. Un remplissage oublié dégrade ici vers le
comportement d'hier, jamais vers le vide. Le prix est deux sources pour la même
valeur, celle-ci et l'amorçage de la migration ; `tests/test_migrations.py`
vérifie qu'elles ne divergent pas.
"""
from collections.abc import Iterable

#: Slugs canoniques (cf. `scrapers/classify.CANONICAL_TYPES`) hors fédération
#: triathlon — l'amorçage de la migration pose ces neuf valeurs.
DEFAULT_NON_FEDERAL_DISCIPLINES: frozenset[str] = frozenset({
    "trail",
    "cyclisme",
    "cyclisme-route",
    "cyclisme-clm",
    "course-a-pied",
    "course-a-pied-5k",
    "course-a-pied-10k",
    "course-a-pied-semi",
    "course-a-pied-marathon",
})

#: Libellés du club sous leur forme normalisée (cf. `club.normalize_club`).
DEFAULT_TCN_CLUB_LABELS: frozenset[str] = frozenset({
    "triathlon club nantais",
    "tri club nantais",
    "tcn",
})

_disciplines: frozenset[str] = DEFAULT_NON_FEDERAL_DISCIPLINES
_club_labels: frozenset[str] = DEFAULT_TCN_CLUB_LABELS


def non_federal_disciplines() -> frozenset[str]:
    """Les disciplines exclues des compteurs, en vigueur."""
    return _disciplines


def tcn_club_labels() -> frozenset[str]:
    """Les libellés reconnus comme libellés du club, en vigueur."""
    return _club_labels


def load(*, disciplines: Iterable[str], club_labels: Iterable[str]) -> None:
    """Remplace les deux ensembles d'un seul geste, **par réassignation**.

    Deux propriétés, et les deux comptent.

    Les deux ensembles ensemble : une configuration à moitié rechargée est un
    état que rien ne doit pouvoir produire.

    Par réassignation, jamais par mutation en place (`add`, `discard`, `clear`) :
    l'import d'épreuve tourne dans un **thread d'arrière-plan** — le scrape SSE
    de `services/import_service` — et appelle `is_tcn` ligne par ligne pendant
    qu'un administrateur peut écrire. Réassigner un nom est atomique du point de
    vue de ce thread ; muter en place lui exposerait un ensemble à moitié écrit,
    et le résultat serait quelques lignes mal classées, sans erreur ni trace.
    """
    global _disciplines, _club_labels
    _disciplines = frozenset(disciplines)
    _club_labels = frozenset(club_labels)


def reset() -> None:
    """Retour aux défauts — fixture de test, et rien d'autre."""
    load(disciplines=DEFAULT_NON_FEDERAL_DISCIPLINES, club_labels=DEFAULT_TCN_CLUB_LABELS)
