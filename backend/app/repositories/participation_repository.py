"""Accès données pour Participation, incluant les filtres de la liste publique."""
from datetime import date

from sqlalchemy import and_, case, func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.club import TCN_KEYWORDS, club_keyword_filter
from app.core.season import season_bounds, season_of
from app.models.athlete import Athlete
from app.models.course import Course
from app.models.participation import Participation


def _is_postgres(db: Session) -> bool:
    """Vrai si le moteur est PostgreSQL (prod) — sinon SQLite (dev)."""
    return db.bind is not None and db.bind.dialect.name == "postgresql"


def _course_name_filter(db: Session, term: str):
    """Filtre nom de course tolérant : trigram pg_trgm (Postgres) sinon ILIKE (SQLite)."""
    like = Course.name.ilike(f"%{term}%")
    if _is_postgres(db):
        # `%` = opérateur de similarité trigram → tolère les fautes de frappe.
        return or_(like, Course.name.op("%")(term))
    return like


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


def update(db: Session, participation: Participation, **fields) -> Participation:
    """Écrit les `fields` fournis sur une participation existante.

    Ne touche que les colonnes passées : le persister a déjà décidé, champ par
    champ, lesquelles la source a le droit de réécrire (fusion prudente).
    """
    for key, value in fields.items():
        setattr(participation, key, value)
    db.flush()
    return participation


def _season_clause(seasons: list[int]):
    """OU de plages de dates pour les saisons demandées (event_date NULL exclu)."""
    bounds = [season_bounds(y) for y in seasons]
    return or_(
        *[and_(Course.event_date >= start, Course.event_date <= end) for start, end in bounds]
    )


def _apply_filters(
    q,
    db,
    *,
    name,
    event_type,
    event_name,
    club,
    date_from,
    date_to,
    course_id=None,
    seasons=None,
):
    """Joint Athlete + Course et applique les filtres communs (liste + épreuves)."""
    q = q.join(Athlete, Participation.athlete_id == Athlete.id).join(
        Course, Participation.course_id == Course.id
    )
    if course_id is not None:
        q = q.filter(Participation.course_id == course_id)
    if name:
        pattern = f"%{name}%"
        q = q.filter(or_(Athlete.nom.ilike(pattern), Athlete.prenom.ilike(pattern)))
    clause = club_keyword_filter(Participation.club, club)
    if clause is not None:
        q = q.filter(clause)
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if event_name:
        q = q.filter(_course_name_filter(db, event_name))
    if date_from:
        q = q.filter(Course.event_date >= date_from)
    if date_to:
        q = q.filter(Course.event_date <= date_to)
    if seasons:
        q = q.filter(_season_clause(seasons))
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
    course_id: int | None = None,
    seasons: list[int] | None = None,
    page: int = 1,
    page_size: int = 20,
) -> list[Participation]:
    q = db.query(Participation).options(
        joinedload(Participation.athlete), joinedload(Participation.course)
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        course_id=course_id,
        seasons=seasons,
    )
    offset = (page - 1) * page_size
    # Pour le détail d'une épreuve, trier par classement ; sinon par date d'import.
    order = (
        (Participation.rank_overall.is_(None), Participation.rank_overall)
        if course_id
        else (Participation.created_at.desc(),)
    )
    return q.order_by(*order).offset(offset).limit(page_size).all()


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
    return club_keyword_filter(Participation.club, "|".join(TCN_KEYWORDS))


def for_stats(
    db: Session, club: str | None = None, seasons: list[int] | None = None
) -> list[Participation]:
    """Charge les participations (avec course + athlète) pour les agrégations stats."""
    q = db.query(Participation).options(
        joinedload(Participation.course), joinedload(Participation.athlete)
    )
    clause = club_keyword_filter(Participation.club, club)
    if clause is not None:
        q = q.filter(clause)
    if seasons:
        q = q.join(Course, Participation.course_id == Course.id).filter(_season_clause(seasons))
    return q.all()


def _grouped_events_query(
    db: Session,
    *,
    name=None,
    event_type=None,
    event_name=None,
    club=None,
    date_from=None,
    date_to=None,
    seasons=None,
):
    """Requête de base : une ligne par épreuve (course) avec compteurs total + TCN."""
    q = db.query(
        Course.id.label("course_id"),
        Course.name.label("event_name"),
        Course.event_date.label("event_date"),
        Course.event_type.label("event_type"),
        Course.is_relay.label("is_relay"),
        Course.distance_km.label("distance_km"),
        func.count(Participation.id).label("total"),
        func.sum(case((tcn_filter(), 1), else_=0)).label("tcn_count"),
    )
    q = _apply_filters(
        q,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
    )
    return q.group_by(
        Course.id,
        Course.name,
        Course.event_date,
        Course.event_type,
        Course.is_relay,
        Course.distance_km,
    )


def events_with_counts(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    seasons: list[int] | None = None,
) -> list:
    """Épreuves distinctes avec total participants et compte TCN (non paginé — carte/stats)."""
    return (
        _grouped_events_query(
            db,
            name=name,
            event_type=event_type,
            event_name=event_name,
            club=club,
            date_from=date_from,
            date_to=date_to,
            seasons=seasons,
        )
        .order_by(Course.event_date.desc().nullslast(), Course.name)
        .all()
    )


def _events_order(db: Session, sort: str, event_name: str | None):
    """Ordre de tri des épreuves. Si recherche fuzzy (Postgres), tri par similarité."""
    if event_name and _is_postgres(db):
        return (
            func.similarity(Course.name, event_name).desc(),
            Course.event_date.desc().nullslast(),
        )
    if sort == "date_asc":
        return (Course.event_date.asc().nullslast(), Course.name)
    if sort == "name":
        return (Course.name.asc(), Course.event_date.desc())
    # date_desc par défaut : dates nulles en dernier.
    return (Course.event_date.desc().nullslast(), Course.name)


def events_page(
    db: Session,
    *,
    name: str | None = None,
    event_type: str | None = None,
    event_name: str | None = None,
    club: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    seasons: list[int] | None = None,
    sort: str = "date_desc",
    page: int = 1,
    page_size: int = 30,
) -> dict:
    """Page d'épreuves (scroll infini) + total épreuves et total participations."""
    grouped = _grouped_events_query(
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
    )

    total_events = db.query(func.count()).select_from(grouped.subquery()).scalar() or 0

    parts = db.query(func.count(Participation.id))
    parts = _apply_filters(
        parts,
        db,
        name=name,
        event_type=event_type,
        event_name=event_name,
        club=club,
        date_from=date_from,
        date_to=date_to,
        seasons=seasons,
    )
    total_participations = parts.scalar() or 0

    offset = (page - 1) * page_size
    rows = (
        grouped.order_by(*_events_order(db, sort, event_name))
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return {
        "items": rows,
        "total_events": int(total_events),
        "total_participations": int(total_participations),
    }


def distinct_seasons(db: Session, club: str | None = None) -> list[dict]:
    """Saisons présentes (≥ 1 participation sur une épreuve datée), repliées en Python.

    Repli Python plutôt que SQL pour rester portable SQLite/Postgres sans
    fonctions de date spécifiques. Volume de données modeste.
    """
    q = (
        db.query(
            Course.event_date.label("event_date"),
            func.count(Participation.id).label("part_count"),
        )
        .join(Participation, Participation.course_id == Course.id)
        .filter(Course.event_date.isnot(None))
    )
    clause = club_keyword_filter(Participation.club, club)
    if clause is not None:
        q = q.filter(clause)
    rows = q.group_by(Course.id, Course.event_date).all()

    agg: dict[int, dict] = {}
    for event_date, part_count in rows:
        year = season_of(event_date)
        entry = agg.setdefault(
            year, {"start_year": year, "event_count": 0, "participation_count": 0}
        )
        entry["event_count"] += 1
        entry["participation_count"] += int(part_count or 0)
    return list(agg.values())
