"""Un calcul coûteux gardé en mémoire de **processus** (#1352, #1384).

Les revues d'administration (doublons d'épreuves, identités) rejouaient leur
détection entière à chaque affichage de leur liste et de leur pastille, et le
backend n'a qu'un process : la rafale retardait les données de la page
elle-même. Le résultat vit ici le temps de `ttl_seconds`, et **tout commit du
process le vide** : une écriture, quelle qu'elle soit, peut changer ces revues
(correction d'une fiche, suppression d'une épreuve, fusion, arbitrage), et la
liste de celles qui le font ne se tiendrait pas à la main. Seules les écritures
commitent : une lecture ne vide rien (`core/database.get_db` ne committe pas).

La **génération** ferme une course : un calcul lent commencé avant un commit ne
réécrit pas sa valeur périmée après lui. Une écriture faite par un autre
process (CLI de batch) ne vide que le sien : la valeur du serveur reste alors
fausse jusqu'à l'expiration.

La valeur rendue est **partagée** entre les requêtes : l'appelant la lit, il ne
la modifie pas.
"""
import threading
import time
from collections.abc import Callable

from sqlalchemy import event
from sqlalchemy.orm import Session

_instances: list["CachedValue"] = []


class CachedValue[T]:
    def __init__(self, ttl_seconds: float):
        self._ttl = ttl_seconds
        self._entry: tuple[float, T] | None = None
        self._generation = 0
        # Deux verrous : un seul calcul à la fois, mais un commit qui vide la
        # valeur n'attend jamais la fin d'un calcul en cours.
        self._compute_lock = threading.Lock()
        self._state_lock = threading.Lock()
        _instances.append(self)

    def _fresh(self) -> tuple[float, T] | None:
        entry = self._entry
        if entry is not None and time.monotonic() - entry[0] < self._ttl:
            return entry
        return None

    def get(self, compute: Callable[[], T]) -> T:
        if entry := self._fresh():
            return entry[1]
        with self._compute_lock:
            if entry := self._fresh():
                return entry[1]
            generation = self._generation
            value = compute()
            with self._state_lock:
                if generation == self._generation:
                    self._entry = (time.monotonic(), value)
            return value

    def clear(self) -> None:
        with self._state_lock:
            self._generation += 1
            self._entry = None


@event.listens_for(Session, "after_commit")
def _clear_all(_session: Session) -> None:
    for instance in _instances:
        instance.clear()
