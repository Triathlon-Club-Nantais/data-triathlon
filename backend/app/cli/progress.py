"""Implémentations d'affichage du ProgressReporter (couche CLI).

Tout sort sur **stderr** : stdout reste réservé au rapport final et à `--json`,
qui doivent rester parsables quand on redirige la sortie.
"""
import sys
import threading
import time
from collections.abc import Callable

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from app.services.progress import NullReporter, ProgressReporter

MAX_LABEL = 60


def truncate(label: str, limit: int = MAX_LABEL) -> str:
    """Borne un libellé pour l'affichage (les URLs de Sheet sont longues)."""
    if len(label) <= limit:
        return label
    return label[: limit - 1] + "…"


def _stderr(ligne: str) -> None:
    print(ligne, file=sys.stderr, flush=True)


def _stderr_is_tty() -> bool:
    """Isolé dans une fonction : c'est le point d'injection des tests."""
    return sys.stderr.isatty()


class PlainReporter:
    """Une ligne par épreuve, sans code ANSI : lisible dans un log (cron, CI, CI/CD).

    Plusieurs chronométreurs peuvent être « en cours » en même temps
    (`services/batch.py`) : l'état (index, libellé, départ) est gardé par
    hôte, et chaque ligne le nomme — sans quoi deux épreuves concurrentes
    produiraient des lignes indiscernables l'une de l'autre dans le log.
    """

    def __init__(self, write: Callable[[str], None] | None = None) -> None:
        self._write = write or _stderr
        self._total = 0
        self._en_cours: dict[str, tuple[int, str, float]] = {}
        self._lock = threading.Lock()

    def batch_start(self, total: int) -> None:
        self._total = total
        self._write(f"=== {total} épreuve(s) à traiter ===")

    def item_start(self, index: int, label: str, host: str) -> None:
        libelle = truncate(label)
        with self._lock:
            self._en_cours[host] = (index, libelle, time.monotonic())
        # Le scrape peut durer une minute : le log ne doit pas rester muet.
        self._write(f"[{index + 1}/{self._total}] ({host}) {libelle} · scraping en cours…")

    def item_progress(self, done: int, total: int, host: str) -> None:
        pass  # le détail intra-épreuve est réservé au mode TTY : ici il inonderait le log

    def item_done(self, imported: int, skipped: int, error: str | None, host: str) -> None:
        with self._lock:
            index, libelle, debut = self._en_cours.pop(host, (0, "", time.monotonic()))
        duree = time.monotonic() - debut
        issue = f"ERREUR : {error}" if error else f"{imported} importés, {skipped} ignorés"
        self._write(f"[{index + 1}/{self._total}] ({host}) {libelle} → {issue} ({duree:.1f}s)")

    def batch_end(self) -> None:
        pass


class RichReporter:
    """Barres imbriquées dans un terminal : le batch, puis une par chronométreur actif.

    Plusieurs chronométreurs tournent en concurrence (`services/batch.py`) :
    une seule tâche « épreuve courante » ne peut plus représenter l'état — une
    tâche Rich par hôte actif est créée à son premier `item_start` et retirée
    à son `item_done`, indépendamment des autres hôtes en cours.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            console=console or Console(stderr=True),
            transient=True,  # les barres s'effacent : le rapport final reste seul
        )
        self._batch_task: int | None = None
        self._item_tasks: dict[str, int] = {}
        self._labels: dict[str, str] = {}
        self._lock = threading.Lock()

    def batch_start(self, total: int) -> None:
        self._progress.start()
        self._batch_task = self._progress.add_task("Épreuves", total=total)

    def item_start(self, index: int, label: str, host: str) -> None:
        libelle = truncate(label)
        with self._lock:
            self._labels[host] = libelle
            # Une tâche par hôte : pas de risque d'hériter du total de
            # l'épreuve précédente, contrairement à une tâche unique réutilisée.
            self._item_tasks[host] = self._progress.add_task(
                f"  ({host}) {libelle} · scraping…", total=None
            )

    def item_progress(self, done: int, total: int, host: str) -> None:
        with self._lock:
            task_id = self._item_tasks.get(host)
            libelle = self._labels.get(host, "")
        if task_id is None:
            return
        self._progress.update(
            task_id,
            completed=done,
            total=total,
            description=f"  ({host}) {libelle} · enregistrement",
        )

    def item_done(self, imported: int, skipped: int, error: str | None, host: str) -> None:
        self._progress.advance(self._batch_task)
        with self._lock:
            task_id = self._item_tasks.pop(host, None)
            libelle = self._labels.pop(host, "")
        if task_id is not None:
            self._progress.remove_task(task_id)
        if error:
            # Les erreurs survivent à l'effacement des barres : on veut les revoir.
            self._progress.console.print(f"  [red]✗[/red] {libelle} → {error}")

    def batch_end(self) -> None:
        self._progress.stop()


def select_reporter(
    *, no_progress: bool = False, plain: bool = False
) -> ProgressReporter:
    """Rich en terminal, lignes simples ailleurs (cron, redirection), rien si --no-progress."""
    if no_progress:
        return NullReporter()
    if plain or not _stderr_is_tty():
        return PlainReporter()
    return RichReporter()
