"""Accès données pour Participation, incluant les filtres de la liste publique."""
from datetime import date

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.club import TCN_KEYWORDS
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation


def get(db: Session, participation_id: int) -> Participation | None:
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete), joinedload(Participation.course))
        .filter(Participation.id == participation_id)
        .first()
    )


def exists_for_bib(db: Session, course_id: int, bib_number: str | None) -> bool:
    if not bib_number:
        return False
    return (
        db.query(Participation.id)
        .filter(Participation.course_id == course_id, Participation.bib_number == bib_number)
        .first()
        is not None
    )


def existing_bibs_for_course(db: Session, course_id: int) -> set[str]:
    """Dossards déjà importés pour une course — pour dédoublonner un import en masse."""
    rows = (
        db.query(Participation.bib_number)
        .filter(Participation.course_id == course_id, Participation.bib_number.isnot(None))
        .all()
    )
    return {r[0] for r in rows}


def create(db: Session, **fields) -> Participation:
    participation = Participation(**fields)
    db.add(participation)
    db.flush()
    return participation


def _apply_filters(q, *, name, event_type, event_name, club, date_from, date_to):
    q = q.join(Athlete, Participation.athlete_id == Athlete.id).join(
        Course, Participation.course_id == Course.id
    )
    if name:
        pattern = f"%{name}%"
        q = q.filter(or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern)))
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if event_name:
        q = q.filter(Course.name.ilike(f"%{event_name}%"))
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)
    return q


def list_participations(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Participation]:
    q = db.query(Participation).options(
        joinedload(Participation.athlete), joinedload(Participation.course)
    )
    q = _apply_filters(
        q,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
    )
    offset = (page - 1) * page_size
    return (
        q.order_by(Participation.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )


def list_for_athlete(db: Session, athlete_id: int) -> list[Participation]:
    return (
        db.query(Participation)
        .options(joinedload(Participation.course))
        .filter(Participation.athlete_id == athlete_id)
        .order_by(Participation.created_at.desc())
        .all()
    )


def list_for_course(db: Session, course_id: int) -> list[Participation]:
    return (
        db.query(Participation)
        .options(joinedload(Participation.athlete))
        .filter(Participation.course_id == course_id)
        .order_by(Participation.rank_overall.is_(None), Participation.rank_overall)
        .all()
    )


def tcn_filter():
    """Clause SQLAlchemy : la participation appartient au TCN (mots-clés club)."""
    return or_(*[Participation.club.ilike(f"%{k}%") for k in TCN_KEYWORDS])


def for_stats(db: Session, club: str | None = None) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    return q.all()


def events_with_counts(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list:
    """Épreuves distinctes (nom, date, type) avec total participants et compte TCN."""
    from sqlalchemy import case, func

    q = db.query(
        Course.name.label("event_name"),
        Course.event_date.label("event_date"),
        Course.event_type.label("event_type"),
        func.count(Participation.id).label("total"),
        func.sum(case((tcn_filter(), 1), else_=0)).label("tcn_count"),
    ).join(Course, Participation.course_id == Course.id)
    q = q.join(Athlete, Participation.athlete_id == Athlete.id)

    if name:
        pattern = f"%{name}%"
        q = q.filter(or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern)))
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        if keywords:
            q = q.filter(or_(*[Participation.club.ilike(f"%{k}%") for k in keywords]))
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if event_name:
        q = q.filter(Course.name.ilike(f"%{event_name}%"))
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)

    return (
        q.group_by(Course.name, Course.event_date, Course.event_type)
        .order_by(Course.event_date.desc(), Course.name)
        .all()
    )
