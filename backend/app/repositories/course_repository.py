"""Accès données pour Course."""
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.club import tcn_clause
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


def list_by_source_url(db: Session, source_url: str) -> list[Course]:
    """Toutes les `Course` publiées sous cette URL d'import — les heats.

    Une URL peut porter N courses (Klikego heats, Wiclax multi-catégories,
    RaceResult multi-listes, Chronoplace multi-épreuves). Alimente le SSE
    `done` sur le chemin cache TTL pour que le sélecteur de course du front
    (#135) rende **toutes** les courses touchées, pas la seule représentative
    de `get_latest_by_source_url`.

    Ordre stable, sur la même clé de tri que le repli latest : `scraped_at`
    décroissant → la plus récente en tête (comportement de la première course
    pré-sélectionnée du sélecteur).
    """
    return (
        db.query(Course)
        .filter(Course.source_url == source_url)
        .order_by(Course.scraped_at.desc())
        .all()
    )


def list_by_source_urls(db: Session, source_urls: list[str]) -> list[Course]:
    """Une seule requête IN pour un lot d'URLs — évite le N+1 sur les heats cachés.

    Utilisé par le SSE `done` du fan-out Klikego (#156) : quand k heats sur N
    sont sautés par le cache TTL, on récupère leurs `Course` déjà en base pour
    étoffer le sélecteur de fin d'import. Sans lot, un import à 20 heats cachés
    ferait 20 requêtes à la place d'une.

    Liste vide → requête évitée, retour `[]`.
    """
    if not source_urls:
        return []
    return (
        db.query(Course)
        .filter(Course.source_url.in_(source_urls))
        .order_by(Course.scraped_at.desc())
        .all()
    )


def touch_scraped_at(db: Session, course: Course) -> None:
    """Met à jour l'horodatage de scraping (clé du cache TTL)."""
    course.scraped_at = utcnow()


def delete(db: Session, course: Course) -> None:
    """Supprime l'épreuve **et tous ses résultats** (#117, FR-002).

    La cascade est portée par la relation (`cascade="all, delete-orphan"`), donc
    par l'**ORM** et non par la base. C'est délibéré : `database.py` n'émet aucun
    `PRAGMA foreign_keys=ON`, un `ondelete="CASCADE"` serait inerte en SQLite
    (développement et tests) et actif en PostgreSQL — un comportement que la
    suite de tests ne verrait jamais.

    ponytail: la cascade ORM charge les participations et émet un DELETE par
    ligne — quelques secondes pour une épreuve de 3 000 finishers, sur un geste
    d'administration ponctuel. Si le volume change de nature, la sortie est un
    delete en masse plus un `ondelete` en base, avec le PRAGMA qui va avec.
    """
    db.delete(course)


def set_quality(
    db: Session,
    course: Course,
    *,
    is_reliable_computed: bool,
    quality_issues: dict[str, int],
) -> None:
    """Persiste l'indice de fiabilité **calculé** à l'import (cf. services/quality.py).

    Écrit `is_reliable_computed`, jamais `reliability_override` : l'avis d'un
    humain survit à tous les re-scrapes, et aucune garde n'est nécessaire pour
    cela — les deux colonnes sont distinctes (FR-037).
    """
    course.is_reliable_computed = is_reliable_computed
    course.quality_issues = quality_issues


def list_all(
    db: Session,
    *,
    event_type: str | None = None,
    club_only: bool = False,
    page: int = 1,
    page_size: int = 50,
) -> list[Course]:
    from app.models.participation import Participation

    q = db.query(Course)
    if event_type:
        q = q.filter(Course.event_type == event_type)
    if club_only:
        q = (
            q.join(Participation, Participation.course_id == Course.id)
            .filter(tcn_clause(Participation.club))
            .distinct()
        )
    offset = (page - 1) * page_size
    return (
        q.order_by(Course.event_date.desc().nullslast(), Course.name)
        .offset(offset)
        .limit(page_size)
        .all()
    )


def iter_all(
    db: Session,
    *,
    provider: str | None = None,
    older_than_days: int | None = None,
) -> list[Course]:
    """Toutes les courses (non paginé), filtrables par provider et ancienneté de scraped_at.

    Alimente le rescrape en masse ; l'accès DB reste confiné au repository.
    """
    q = db.query(Course)
    if provider:
        q = q.filter(Course.provider == provider)
    if older_than_days is not None:
        cutoff = utcnow() - timedelta(days=older_than_days)
        q = q.filter(Course.scraped_at < cutoff)
    return q.order_by(Course.event_date.desc().nullslast(), Course.name).all()


def update_identity(db: Session, course: Course, **champs) -> Course:
    """Écrit les champs d'identité fournis. **Ne vérifie pas l'unicité** — c'est
    le service qui la contrôle par lecture préalable, pour pouvoir nommer
    l'épreuve en conflit (#117, FR-021)."""
    for nom_champ, valeur in champs.items():
        setattr(course, nom_champ, valeur)
    db.flush()
    return course
