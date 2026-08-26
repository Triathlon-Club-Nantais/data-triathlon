"""Arriéré de la file bénévole et délai moyen de résolution (US13, #466)."""
from datetime import date, timedelta

from app.repositories.participation_repository import ValidationQueueTimestamps
from app.schemas.validation_queue import ValidationQueueBacklogPoint, ValidationQueueHistory


def build_history(donnees: ValidationQueueTimestamps, *, aujourdhui: date) -> ValidationQueueHistory:
    """`aujourdhui` est injecté par l'appelant (jamais `date.today()` ici) : la
    fonction reste pure et déterministe, testable sans horloge système."""
    return ValidationQueueHistory(
        backlog_by_day=[
            ValidationQueueBacklogPoint(date=jour, pending_count=compte)
            for jour, compte in _backlog_by_day(donnees, aujourdhui)
        ],
        average_resolution_seconds=_average_resolution_seconds(donnees),
    )


def _backlog_by_day(donnees: ValidationQueueTimestamps, aujourdhui: date) -> list[tuple[date, int]]:
    """Balayage par delta (+1 à l'entrée, -1 à la sortie) plutôt qu'un comptage
    jour par jour par entrée : coût en `O(entrées + jours)`, pas
    `O(entrées × jours)` — une entrée actionnable de longue date ne doit pas
    faire exploser le calcul."""
    deltas: dict[date, int] = {}
    debut: date | None = None

    def _ajoute(depart: date, fin_exclusive: date) -> None:
        nonlocal debut
        if fin_exclusive <= depart:
            return
        debut = depart if debut is None else min(debut, depart)
        deltas[depart] = deltas.get(depart, 0) + 1
        deltas[fin_exclusive] = deltas.get(fin_exclusive, 0) - 1

    for created_at in donnees.actionable_since:
        _ajoute(created_at.date(), aujourdhui + timedelta(days=1))
    for created_at, validated_at in donnees.validated:
        _ajoute(created_at.date(), validated_at.date())
    for created_at, rejected_at in donnees.rejected:
        _ajoute(created_at.date(), rejected_at.date())

    if debut is None:
        return []

    resultat: list[tuple[date, int]] = []
    total = 0
    jour = debut
    while jour <= aujourdhui:
        total += deltas.get(jour, 0)
        resultat.append((jour, total))
        jour += timedelta(days=1)
    return resultat


def _average_resolution_seconds(donnees: ValidationQueueTimestamps) -> int | None:
    durees = [
        (resolu - cree).total_seconds() for cree, resolu in (*donnees.validated, *donnees.rejected)
    ]
    if not durees:
        return None
    return round(sum(durees) / len(durees))
