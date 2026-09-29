"""Identités d'épreuves absorbées par une fusion, et leur cible (#983)."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.absorbed_course import AbsorbedCourse
from app.models.course import Course


def record(db: Session, *, absorbed: Course, target: Course) -> None:
    """Retient l'identité publiée de `absorbed`, absorbée par `target`.

    À appeler **avant** la suppression de l'absorbée : après, elle n'a plus de
    source active à nommer. Sans URL (saisie manuelle), rien ne la republiera.
    """
    if not absorbed.source_url:
        return
    db.add(
        AbsorbedCourse(
            target=target,
            url=absorbed.source_url,
            name=absorbed.name,
            event_date=absorbed.event_date,
            event_type=absorbed.event_type,
            is_relay=absorbed.is_relay,
        )
    )


def repoint(db: Session, *, source: Course, target: Course) -> None:
    """Les identités absorbées par `source` passent à `target`.

    Par la relation, comme `course_source_repository.move_to` : c'est ce qui les
    retire de `source.absorbed`, sans quoi la cascade les supprimerait au
    `delete` de `source` qui suit.
    """
    for absorbed in list(source.absorbed):
        absorbed.target = target


def is_absorbed(
    db: Session,
    *,
    url: str,
    name: str,
    event_date: date | None,
    event_type: str,
    is_relay: bool,
) -> bool:
    """Vrai si une fusion a absorbé cette identité publiée sous cette URL."""
    query = (
        select(AbsorbedCourse.id)
        .where(
            AbsorbedCourse.url == url,
            AbsorbedCourse.name == name,
            AbsorbedCourse.event_type == event_type,
            AbsorbedCourse.is_relay == is_relay,
            AbsorbedCourse.event_date.is_(None)
            if event_date is None
            else AbsorbedCourse.event_date == event_date,
        )
        .limit(1)
    )
    return db.scalars(query).first() is not None
