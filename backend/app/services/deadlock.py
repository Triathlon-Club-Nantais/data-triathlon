"""Rejeu d'une transaction sur deadlock PostgreSQL (`40P01`, #771, #980).

Un seul rejeu pour tous les chemins d'écriture : `import_event`,
`iter_import_event`, le re-scrape admin et la bascule de source. Avant #980,
seul le flux SSE rejouait ; les autres perdaient l'épreuve entière au premier
deadlock.

Forme d'emploi, valable aussi dans un générateur (un `yield` peut vivre dans
le bloc) :

    for attempt in deadlock_retries(db, label=url):
        with attempt:
            ...  # écritures, puis commit

Un deadlock avant le dernier essai est absorbé : la transaction est annulée,
une courte pause aléatoire écarte les deux transactions, et le corps repart
d'une transaction propre. Toute autre erreur, ou un deadlock au dernier essai,
remonte telle quelle.
"""
import logging
import random
import time
from collections.abc import Iterator

import psycopg.errors
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3


def is_deadlock(exc: BaseException) -> bool:
    """Le SQLSTATE `40P01`, que psycopg 3 porte par `DeadlockDetected`,
    indépendamment du message (localisable)."""
    return isinstance(getattr(exc, "orig", None), psycopg.errors.DeadlockDetected)


class _Attempt:
    def __init__(self, db: Session, number: int, label: str, state: dict) -> None:
        self._db = db
        self.number = number
        self._label = label
        self._state = state

    def __enter__(self) -> "_Attempt":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc is None:
            self._state["done"] = True
            return False
        if not is_deadlock(exc) or self.number >= MAX_ATTEMPTS:
            return False
        self._db.rollback()
        logger.warning(
            "Deadlock Postgres pour %s (tentative %d/%d), nouvel essai",
            self._label, self.number, MAX_ATTEMPTS, exc_info=exc,
        )
        time.sleep(random.uniform(0.05, 0.2) * self.number)  # noqa: S311 — jitter anti-collision, pas cryptographique
        return True


def deadlock_retries(db: Session, *, label: str) -> Iterator[_Attempt]:
    state = {"done": False}
    for number in range(1, MAX_ATTEMPTS + 1):
        yield _Attempt(db, number, label, state)
        if state["done"]:
            return
