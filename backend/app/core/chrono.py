"""Temps de course « absent » — **seule** définition du dépôt.

Un chronométreur rend un temps manquant de plusieurs façons : colonne vide,
absente, ou remplie de zéros pendant qu'il publie sa liste de départ. Les trois
disent la même chose, et trois modules en dépendent pour des raisons
différentes — l'indice de fiabilité (`services/quality`), le TTL du cache
(`services/cache`) et l'ordre du classement
(`repositories/participation_repository`). Ils divergeaient : chacun portait sa
propre liste, la plus courte tenant `00:00:00` pour un temps final.

Vit dans `core` et pas dans un service parce que la couche repository en dépend
aussi, et qu'elle ne remonte jamais vers les services.
"""

#: Les formes que prend un temps total nul selon les fournisseurs.
ZERO_TIMES = frozenset({"", "00:00:00", "0:00:00", "00:00", "0:00", "0"})


def has_no_time(total_time: str | None) -> bool:
    """Vrai si ce temps total n'en est pas un (côté Python ; en SQL : `ZERO_TIMES`)."""
    return (total_time or "").strip() in ZERO_TIMES
