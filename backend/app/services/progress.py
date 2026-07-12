"""Contrat de progression des batches d'import.

Les services d'orchestration notifient un reporter au fil de l'eau sans rien
connaître de Typer ni de Rich (inversion de dépendance, comme le registre
Protocol des scrapers). Le défaut `NullReporter` les garde muets et testables
sans terminal ; la couche CLI branche ses propres implémentations.
"""
from typing import Protocol, runtime_checkable


@runtime_checkable
class ProgressReporter(Protocol):
    """Reçoit la progression d'un batch : le batch, puis chaque épreuve."""

    def batch_start(self, total: int) -> None:
        """Le batch démarre avec `total` épreuves à traiter."""
        ...

    def item_start(self, index: int, label: str) -> None:
        """L'épreuve n° `index` (0-based) démarre, identifiée par `label`."""
        ...

    def item_progress(self, done: int, total: int) -> None:
        """Progression *dans* l'épreuve courante : `done`/`total` participants."""
        ...

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        """L'épreuve courante est terminée — ou en échec si `error` est renseigné."""
        ...

    def batch_end(self) -> None:
        """Le batch est terminé (y compris s'il a été interrompu)."""
        ...


class NullReporter:
    """Ne rapporte rien. Défaut de tous les services."""

    def batch_start(self, total: int) -> None:
        pass

    def item_start(self, index: int, label: str) -> None:
        pass

    def item_progress(self, done: int, total: int) -> None:
        pass

    def item_done(self, imported: int, skipped: int, error: str | None) -> None:
        pass

    def batch_end(self) -> None:
        pass
