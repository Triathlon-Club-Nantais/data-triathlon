"""Accès données pour Course."""
from datetime import date

from sqlalchemy.orm import Session

from app.core.club import club_keyword_filter
from app.core.time import utcnow
from app.models.course import Course


def get(db: Session, course_id: int) -> Course | None:
    return db.get(Course, course_id)


def get_by_identity(
    db: Session,
    name: str,
    event_date: date | None,
    event_type: str,
    is_relay: bool,
) -> Course | None:
    return (
        db.query(Course)
        .filter(
            Course.name == name,
            Course.event_date == event_date,
            Course.event_type == event_type,
            Course.is_relay == is_relay,
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
    existing = get_by_identity(db, name, event_date, event_type, is_relay)
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


def set_quality(
    db: Session, course: Course, *, is_reliable: bool, quality_issues: dict[str, int]
) -> None:
    """Persiste l'indice de fiabilité calculé à l'import (cf. services/quality.py)."""
    course.is_reliable = is_reliable
    course.quality_issues = quality_issues


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
    clause = club_keyword_filter(Participation.club, club)
    if clause is not None:
        q = (
            q.join(Participation, Participation.course_id == Course.id)
            .filter(clause)
            .distinct()
        )
    offset = (page - 1) * page_size
    return (
        q.order_by(Course.event_date.desc().nullslast(), Course.name)
        .offset(offset)
        .limit(page_size)
        .all()
    )
