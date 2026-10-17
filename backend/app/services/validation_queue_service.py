"""Arriéré de la file bénévole et délai moyen de résolution (US13, #466)."""
from datetime import date, timedelta

from app.repositories.participation_repository import ValidationQueueTimestamps
from app.schemas.validation_queue import ValidationQueueBacklogPoint, ValidationQueueHistory


def build_history(timestamps: ValidationQueueTimestamps, *, today: date) -> ValidationQueueHistory:
    """`today` est injecté par l'appelant (jamais `date.today()` ici) : la
    fonction reste pure et déterministe, testable sans horloge système."""
    return ValidationQueueHistory(
        backlog_by_day=[
            ValidationQueueBacklogPoint(date=day, pending_count=count)
            for day, count in _backlog_by_day(timestamps, today)
        ],
        average_resolution_seconds=_average_resolution_seconds(timestamps),
    )


def _backlog_by_day(timestamps: ValidationQueueTimestamps, today: date) -> list[tuple[date, int]]:
    """Balayage par delta (+1 à l'entrée, -1 à la sortie) plutôt qu'un comptage
    jour par jour par entrée : coût en `O(entrées + jours)`, pas
    `O(entrées × jours)` — une entrée actionnable de longue date ne doit pas
    faire exploser le calcul."""
    deltas: dict[date, int] = {}
    first_day: date | None = None

    def _add(start: date, end_exclusive: date) -> None:
        nonlocal first_day
        if end_exclusive <= start:
            return
        first_day = start if first_day is None else min(first_day, start)
        deltas[start] = deltas.get(start, 0) + 1
        deltas[end_exclusive] = deltas.get(end_exclusive, 0) - 1

    for created_at in timestamps.actionable_since:
        _add(created_at.date(), today + timedelta(days=1))
    for created_at, validated_at in timestamps.validated:
        _add(created_at.date(), validated_at.date())
    for created_at, rejected_at in timestamps.rejected:
        _add(created_at.date(), rejected_at.date())

    if first_day is None:
        return []

    result: list[tuple[date, int]] = []
    total = 0
    day = first_day
    while day <= today:
        total += deltas.get(day, 0)
        result.append((day, total))
        day += timedelta(days=1)
    return result


def _average_resolution_seconds(timestamps: ValidationQueueTimestamps) -> int | None:
    durations = [
        (resolved - created).total_seconds() for created, resolved in (*timestamps.validated, *timestamps.rejected)
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations))
