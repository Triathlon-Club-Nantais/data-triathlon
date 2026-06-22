"""
Détection du club TCN.

Centralise les mots-clés (auparavant dupliqués dans results.py et stats.py) et
la logique d'appartenance au club, car les noms varient :
« TCN », « TRIATHLON CLUB NANTAIS », « nantais »…
"""

TCN_KEYWORDS: tuple[str, ...] = ("nantais", "tcn", "triathlon club nant")


def is_tcn(club: str | None) -> bool:
    """Vrai si la chaîne `club` correspond au Triathlon Club Nantais."""
    if not club:
        return False
    low = club.lower()
    return any(k in low for k in TCN_KEYWORDS)
