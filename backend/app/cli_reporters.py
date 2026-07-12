"""Implémentations d'affichage du ProgressReporter (couche CLI).

Tout sort sur **stderr** : stdout reste réservé au rapport final et à `--json`,
qui doivent rester parsables quand on redirige la sortie.
"""
import sys
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
    """Une ligne par épreuve, sans code ANSI : lisible dans un log (cron, CI, CI/CD)."""

    def __init__(self, write: Callable[[str], None] | None = None) -> None:
        self._write = write or _stderr
        self._total = 0
        self._index = 0
        self._label = ""
        self._debut = 0.0

    def batch_start(self, total: int) -> None:
        self._total = total
        self._write(f"=== {total} épreuve(s) à traiter ===")

    def item_start(self, index: int, label: str) -> None:
        self._index = index
        self._label = truncate(label)
        self._debut = time.monotonic()
        # Le scrape peut durer une minute : le log ne doit pas rester muet.
        self._write(f"[{index + 1}/{self._total}] {self._label} · scraping en cours…")

    def item_progress(self, done: int, total: int) -> None:
        pass  # le détail intra-épreuve est réservé au mode TTY : ici il inonderait le log

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        duree = time.monotonic() - self._debut
        issue = f"ERREUR : {error}" if error else f"{imported} importés, {skipped} ignorés"
        self._write(f"[{self._index + 1}/{self._total}] {self._label} → {issue} ({duree:.1f}s)")

    def batch_end(self) -> None:
        pass


class RichReporter:
    """Deux barres imbriquées dans un terminal : le batch, puis l'épreuve courante."""

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
        self._item_task: int | None = None
        self._label = ""

    def batch_start(self, total: int) -> None:
        self._progress.start()
        self._batch_task = self._progress.add_task("Épreuves", total=total)
        self._item_task = self._progress.add_task("En attente…", total=None)

    def item_start(self, index: int, label: str) -> None:
        self._label = truncate(label)
        self._progress.reset(
            self._item_task, total=None, description=f"  {self._label} · scraping…"
        )

    def item_progress(self, done: int, total: int) -> None:
        self._progress.update(
            self._item_task,
            completed=done,
            total=total,
            description=f"  {self._label} · enregistrement",
        )

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        self._progress.advance(self._batch_task)
        if error:
            # Les erreurs survivent à l'effacement des barres : on veut les revoir.
            self._progress.console.print(f"  [red]✗[/red] {self._label} → {error}")

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
