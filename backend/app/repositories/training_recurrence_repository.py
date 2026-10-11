"""Accès données pour TrainingRecurrence (#1291). On `flush()`, jamais de `commit()`."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.training_group import TrainingGroup
from app.models.training_recurrence import TrainingRecurrence
from app.models.training_session import TrainingSession


def get(db: Session, recurrence_id: int) -> TrainingRecurrence | None:
    return db.get(TrainingRecurrence, recurrence_id)


def list_all(db: Session) -> list[TrainingRecurrence]:
    return list(
        db.scalars(
            select(TrainingRecurrence)
            .options(selectinload(TrainingRecurrence.groups))
            .order_by(TrainingRecurrence.weekday, TrainingRecurrence.start_time, TrainingRecurrence.id)
        )
    )


def create(db: Session, *, groups: list[TrainingGroup], **fields) -> TrainingRecurrence:
    recurrence = TrainingRecurrence(groups=groups, **fields)
    db.add(recurrence)
    db.flush()
    return recurrence


def update(db: Session, recurrence: TrainingRecurrence, **fields) -> TrainingRecurrence:
    for field, value in fields.items():
        setattr(recurrence, field, value)
    db.flush()
    return recurrence


def delete(db: Session, recurrence: TrainingRecurrence) -> None:
    db.delete(recurrence)
    db.flush()


def list_sessions(db: Session, recurrence_id: int) -> list[TrainingSession]:
    return list(
        db.scalars(
            select(TrainingSession)
            .where(TrainingSession.recurrence_id == recurrence_id)
            .order_by(TrainingSession.date)
        )
    )
