"""Schémas Pydantic de l'historique de la file bénévole (US13, #466)."""
from datetime import date

from pydantic import BaseModel


class ValidationQueueBacklogPoint(BaseModel):
    """Nombre de résultats en attente actionnable à la fin d'un jour donné."""

    date: date
    pending_count: int


class ValidationQueueHistory(BaseModel):
    """Réponse de `GET /api/v1/benevoles/queue/history`.

    `backlog_by_day` ne remonte que jusqu'au déploiement de
    `Participation.validated_at`/`.rejected_at` — aucune antériorité
    reconstructible (`data-model.md` de la feature).
    """

    backlog_by_day: list[ValidationQueueBacklogPoint]
    #: `None` tant qu'aucune résolution n'a de timestamp exploitable.
    average_resolution_seconds: int | None = None
