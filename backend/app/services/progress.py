"""Contrat de progression des batches d'import.

Les services d'orchestration notifient un reporter au fil de l'eau sans rien
connaître de Typer ni de Rich (inversion de dépendance, comme le registre
Protocol des scrapers). Le défaut `NullReporter` les garde muets et testables
sans terminal ; la couche CLI branche ses propres implémentations.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Reçoit la progression d'un batch : le batch, puis chaque épreuve.

    `host` identifie le chronométreur qui traite l'épreuve : plusieurs hôtes
    tournent en concurrence (`services/batch.py`), donc plusieurs épreuves
    peuvent être « en cours » en même temps — `index`/`label` seuls ne
    suffisent plus à savoir laquelle chaque appel concerne.
    """

    def batch_start(self, total: int) -> None:
        """Le batch démarre avec `total` épreuves à traiter."""

    def item_start(self, index: int, label: str, host: str) -> None:
        """L'épreuve n° `index` (0-based) démarre, identifiée par `label`."""

    def item_progress(self, done: int, total: int, host: str) -> None:
        """Progression *dans* l'épreuve en cours sur `host` : `done`/`total` participants."""

    def item_done(self, imported: int, skipped: int, error: str | None, host: str) -> None:
        """L'épreuve en cours sur `host` est terminée — ou en échec si `error` est renseigné."""

    def batch_end(self) -> None:
        """Le batch est terminé (y compris s'il a été interrompu)."""


class NullReporter:
    """Ne rapporte rien. Défaut de tous les services."""

    def batch_start(self, total: int) -> None:
        pass

    def item_start(self, index: int, label: str, host: str) -> None:
        pass

    def item_progress(self, done: int, total: int, host: str) -> None:
        pass

    def item_done(self, imported: int, skipped: int, error: str | None, host: str) -> None:
        pass

    def batch_end(self) -> None:
        pass
