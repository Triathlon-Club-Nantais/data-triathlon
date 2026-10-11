"""Séances récurrentes hebdomadaires (#1291, US3, research R4).

Une récurrence engendre une séance par occurrence de sa période. Ses
modifications et sa suppression ne touchent que les séances qu'elle peut encore
gouverner : à venir, sans appel commencé, jamais modifiées seules (FR-010)."""
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.training_recurrence import TrainingRecurrence
from app.models.user import User
from app.repositories import training_recurrence_repository, training_session_repository
from app.services import training_session_service

logger = logging.getLogger(__name__)

#: Une saison sportive au plus (FR-012).
MAX_OCCURRENCES = 53

_SESSION_FIELDS = ("start_time", "location", "session_type")


class InvalidRecurrenceError(DomainError):
    status_code = 422


def occurrence_dates(weekday: int, starts_on: date, ends_on: date) -> list[date]:
    if ends_on < starts_on:
        raise InvalidRecurrenceError("La date de fin précède la date de début.")
    first = starts_on + timedelta(days=(weekday - starts_on.weekday()) % 7)
    count = 0 if first > ends_on else (ends_on - first).days // 7 + 1
    if count == 0:
        raise InvalidRecurrenceError("Aucune séance dans cette période.")
    if count > MAX_OCCURRENCES:
        raise InvalidRecurrenceError(
            f"Une récurrence compte au plus {MAX_OCCURRENCES} séances : raccourcissez la période."
        )
    return [first + timedelta(weeks=week) for week in range(count)]


def get_recurrence_or_404(db: Session, recurrence_id: int) -> TrainingRecurrence:
    recurrence = training_recurrence_repository.get(db, recurrence_id)
    if recurrence is None:
        raise NotFoundError("Cette récurrence n'existe pas.")
    return recurrence


def _governed_sessions(db: Session, recurrence: TrainingRecurrence):
    """Les séances que la récurrence gouverne encore : à venir, sans appel
    commencé, jamais modifiées seules."""
    sessions = training_recurrence_repository.list_sessions(db, recurrence.id)
    started = training_session_repository.roll_call_started_among(db, [s.id for s in sessions])
    today = date.today()
    return [s for s in sessions if not s.detached and s.date >= today and s.id not in started]


def recurrence_view(db: Session, recurrence: TrainingRecurrence) -> dict:
    return {
        "id": recurrence.id,
        "weekday": recurrence.weekday,
        "start_time": recurrence.start_time,
        "location": recurrence.location,
        "session_type": recurrence.session_type,
        "starts_on": recurrence.starts_on,
        "ends_on": recurrence.ends_on,
        "group_ids": [group.id for group in recurrence.groups],
        # Ce que supprimerait la suppression de la récurrence (FR-020).
        "upcoming_session_count": len(_governed_sessions(db, recurrence)),
    }


def list_recurrence_views(db: Session) -> list[dict]:
    return [recurrence_view(db, recurrence) for recurrence in training_recurrence_repository.list_all(db)]


def _create_session(db: Session, recurrence: TrainingRecurrence, day: date) -> None:
    training_session = training_session_repository.create(
        db,
        date=day,
        start_time=recurrence.start_time,
        location=recurrence.location,
        session_type=recurrence.session_type,
        recurrence_id=recurrence.id,
    )
    training_session_repository.set_groups(db, training_session, list(recurrence.groups))
    training_session_service.sync_group_enrolment(db, training_session)


def create_recurrence(
    db: Session,
    actor: User,
    *,
    weekday: int,
    start_time,
    location: str | None,
    session_type: str | None,
    starts_on: date,
    ends_on: date,
    group_ids: list[int],
) -> tuple[TrainingRecurrence, int]:
    """Rend la récurrence et le nombre de séances créées."""
    dates = occurrence_dates(weekday, starts_on, ends_on)
    recurrence = training_recurrence_repository.create(
        db,
        groups=training_session_service.groups_or_404(db, group_ids),
        weekday=weekday,
        start_time=start_time,
        location=location,
        session_type=session_type,
        starts_on=starts_on,
        ends_on=ends_on,
    )
    for day in dates:
        _create_session(db, recurrence, day)
    logger.info("Training recurrence created: actor=%s recurrence=%s sessions=%s", actor.id, recurrence.id, len(dates))
    return recurrence, len(dates)


def update_recurrence(
    db: Session, actor: User, recurrence: TrainingRecurrence, *, group_ids: list[int] | None = None, **fields
) -> TrainingRecurrence:
    """Seuls les champs fournis changent. Une date ajoutée à la période crée sa
    séance ; une séance supprimée seule n'est jamais recréée."""
    old_dates = set(occurrence_dates(recurrence.weekday, recurrence.starts_on, recurrence.ends_on))
    candidate = {
        name: fields.get(name, getattr(recurrence, name)) for name in ("weekday", "starts_on", "ends_on")
    }
    new_dates = set(occurrence_dates(candidate["weekday"], candidate["starts_on"], candidate["ends_on"]))
    groups = training_session_service.groups_or_404(db, group_ids) if group_ids is not None else None
    groups_changed = groups is not None and set(groups) != set(recurrence.groups)
    if groups_changed:
        fields["groups"] = groups
    training_recurrence_repository.update(db, recurrence, **fields)

    for training_session in _governed_sessions(db, recurrence):
        if training_session.date not in new_dates:
            training_session_repository.delete_training_session(db, training_session)
            continue
        training_session_repository.update(
            db, training_session, **{name: getattr(recurrence, name) for name in _SESSION_FIELDS}
        )
        # Resynchroniser sans changement de groupes réinscrirait un jeune retiré à la main.
        if groups_changed:
            training_session_repository.set_groups(db, training_session, list(recurrence.groups))
            training_session_service.sync_group_enrolment(db, training_session)
    existing = {s.date for s in training_recurrence_repository.list_sessions(db, recurrence.id)}
    for day in sorted(new_dates - old_dates - existing):
        if day >= date.today():
            _create_session(db, recurrence, day)
    logger.info("Training recurrence updated: actor=%s recurrence=%s", actor.id, recurrence.id)
    return recurrence


def delete_recurrence(db: Session, actor: User, recurrence: TrainingRecurrence) -> dict:
    governed = _governed_sessions(db, recurrence)
    kept = [s for s in training_recurrence_repository.list_sessions(db, recurrence.id) if s not in governed]
    for training_session in governed:
        training_session_repository.delete_training_session(db, training_session)
    for training_session in kept:
        training_session_repository.unlink_from_recurrence(db, training_session)
    recurrence_id = recurrence.id
    training_recurrence_repository.delete(db, recurrence)
    logger.info(
        "Training recurrence deleted: actor=%s recurrence=%s deleted=%s kept=%s",
        actor.id,
        recurrence_id,
        len(governed),
        len(kept),
    )
    return {"deleted_session_count": len(governed), "kept_session_count": len(kept)}
