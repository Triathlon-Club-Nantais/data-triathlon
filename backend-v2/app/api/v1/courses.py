"""Router Courses : liste, détail avec participants, épreuves agrégées."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.repositories import course_repository, participation_repository
from app.schemas.course import CourseBrief, EventOut
from app.schemas.participation import ParticipationOut
from app.services import stats_service

router = APIRouter(tags=["courses"])


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@router.get("/courses/events", response_model=list[EventOut])
def list_events(
    name: str | None = Query(None),
    event_type: str | None = Query(None),
    event_name: str | None = Query(None),
    club: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Épreuves distinctes avec compteurs participants + TCN."""
    return stats_service.list_events(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=_parse_date(date_from),
        date_to=_parse_date(date_to),
    )


@router.get("/courses", response_model=list[CourseBrief])
def list_courses(
    event_type: str | None = Query(None),
    club: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return course_repository.list_all(
        db, event_type=event_type, club=club, page=page, page_size=page_size
    )


@router.get("/courses/{course_id}")
def get_course(course_id: int, db: Session = Depends(get_db)):
    course = course_repository.get(db, course_id)
    if not course:
        raise NotFoundError("Course introuvable")
    participations = participation_repository.list_for_course(db, course_id)
    return {
        "course": CourseBrief.model_validate(course),
        "participations": [ParticipationOut.model_validate(p) for p in participations],
    }
