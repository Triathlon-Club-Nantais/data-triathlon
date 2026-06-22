"""Accès données pour Course."""
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.course import Course


def get(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def get_by_identity(
    db: Session, name: str, event_date: date | None, event_type: str
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.name == name,
            Course.event_date == event_date,
            Course.event_type == event_type,
        )
        .first()
    )


def get_or_create(
    db: Session,
    *,
    name: str,
    event_date: date | None,
    event_type: str,
    source_url: str = "",
    provider: str = "",
    is_relay: bool = False,
    distance_km: float | None = None,
) -> Course:
    existing = get_by_identity(db, name, event_date, event_type)
    if existing:
        return existing
    course = Course(
        name=name,
        event_date=event_date,
        event_type=event_type,
        source_url=source_url,
        provider=provider,
        is_relay=is_relay,
        distance_km=distance_km,
    )
    db.add(course)
    db.flush()
    return course


def get_latest_by_source_url(db: Session, source_url: str) -> Course | None:
    """Course la plus récemment scrapée pour cette URL d'import (clé du cache TTL)."""
    return (
        db.query(Course)
        .filter(Course.source_url == source_url)
        .order_by(Course.scraped_at.desc())
        .first()
    )


def touch_scraped_at(db: Session, course: Course) -> None:
    """Met à jour l'horodatage de scraping (clé du cache TTL)."""
    course.scraped_at = utcnow()


def list_all(
    db: Session,
    *,
    event_type: str | None = None,
    club: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> list[Course]:
    from app.models.participation import Participation

    q = db.query(Course)
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = (
                q.join(Participation, Participation.course_id == Course.id)
                .filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
                .distinct()
            )
    offset = (page - 1) * page_size
    return (
        q.order_by(Course.event_date.desc().nullslast(), Course.name)
        .offset(offset)
        .limit(page_size)
        .all()
    )
