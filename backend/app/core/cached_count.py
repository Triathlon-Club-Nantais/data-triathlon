"""Un compte coûteux gardé en mémoire de **processus** (#1352).

Les pastilles du rail (doublons d'épreuves, revue d'identités) rejouaient leur
détection entière à chaque page d'administration, et le backend n'a qu'un
process : la rafale retardait les données de la page elle-même. Le compte vit
ici le temps de `ttl_seconds`, la liste de l'écran le rafraîchit (`set`) et
les arbitrages de l'écran le vident (`clear`). Une écriture faite ailleurs
(fusion depuis une fiche, import) ne le rend faux que jusqu'à l'expiration.

Un seul worker uvicorn en production : un cache partagé entre process ne
servirait à rien. Deux requêtes concurrentes sur un cache froid calculent
toutes les deux, sans autre effet.
"""
import time
from collections.abc import Callable


class CachedCount:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._entry: tuple[float, int] | None = None

    def get(self, compute: Callable[[], int]) -> int:
        entry = self._entry
        if entry is not None and time.monotonic() - entry[0] < self._ttl:
            return entry[1]
        value = compute()
        self.set(value)
        return value

    def set(self, value: int) -> None:
        self._entry = (time.monotonic(), value)

    def clear(self) -> None:
        self._entry = None
