"""
Détection du club TCN.

Centralise les mots-clés (auparavant dupliqués dans results.py et stats.py) et
la logique d'appartenance au club, car les noms varient :
« TCN », « TRIATHLON CLUB NANTAIS », « nantais »…
"""

from sqlalchemy import or_

TCN_KEYWORDS: tuple[str, ...] = ("nantais", "tcn", "triathlon club nant")


def is_tcn(club: str | None) -> bool:
    """Vrai si la chaîne `club` correspond au Triathlon Club Nantais."""
    if not club:
        return False
    low = club.lower()
    return any(k in low for k in TCN_KEYWORDS)


def club_keyword_filter(column, club: str | None):
    """Clause SQLAlchemy : `column` matche l'un des mots-clés de `club`.

    `club` est une liste de mots-clés séparés par « | » (ex. « tcn|nantais ») ;
    chacun est cherché en sous-chaîne insensible à la casse. Retourne `None` si
    `club` est vide ou sans mot-clé exploitable, pour que l'appelant court-circuite
    le filtre. `column` est passée en paramètre pour couvrir aussi bien
    `Participation.club` que `Athlete.club`.
    """
    if not club:
        return None
    keywords = [k.strip() for k in club.split("|") if k.strip()]
    if not keywords:
        return None
    return or_(*[column.ilike(f"%{k}%") for k in keywords])
