"""Un compte coûteux gardé en mémoire de **processus** (#1352).

Les pastilles du rail (doublons d'épreuves, revue d'identités) rejouaient leur
détection entière à chaque page d'administration, et le backend n'a qu'un
process : la rafale retardait les données de la page elle-même. Le compte vit
ici le temps de `ttl_seconds`, et **tout commit du process le vide** : une
écriture, quelle qu'elle soit, peut changer ces comptes (correction d'une fiche,
suppression d'une épreuve, fusion, arbitrage), et la liste de ceux qui le font
ne se tiendrait pas à la main. Seules les écritures commitent : une lecture ne
vide rien (`core/database.get_db` ne committe pas).

La **génération** ferme une course : un calcul lent commencé avant un commit ne
réécrit pas sa valeur périmée après lui. Une écriture faite par un autre
process (CLI de batch) ne vide que le sien : le compte du serveur reste alors
faux jusqu'à l'expiration.
"""
import time
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

_instances: list["CachedCount"] = []


class CachedCount:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._entry: tuple[float, int] | None = None
        self._generation = 0
        _instances.append(self)

    @property
    def generation(self) -> int:
        return self._generation

    def get(self, compute: Callable[[], int]) -> int:
        entry = self._entry
        if entry is not None and time.monotonic() - entry[0] < self._ttl:
            return entry[1]
        generation = self._generation
        value = compute()
        self.set(value, generation)
        return value

    def set(self, value: int, generation: int) -> None:
        """Garde `value`, calculée à `generation`, sauf si un commit est passé depuis."""
        if generation == self._generation:
            self._entry = (time.monotonic(), value)

    def clear(self) -> None:
        self._generation += 1
        self._entry = None


@event.listens_for(Session, "after_commit")
def _clear_all(_session: Session) -> None:
    for instance in _instances:
        instance.clear()
