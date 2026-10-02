"""Classements Challenge (#1008) : appariement aux épreuves du jour, enregistrement.

Un heat dont le nom annonce un Challenge n'en est un que si ses athlètes courent
aussi les autres épreuves du même jour : `MIN_COVERAGE` d'entre eux doivent
figurer sur au moins `MIN_COURSES_PER_ATHLETE` épreuves. Les épreuves liées sont
celles où figure au moins `MIN_LINK_SHARE` du classement.

Une ligne n'est jamais créatrice d'athlète : sans appariement unique, elle est
écartée. Une personne opposée (#334) ou un nom masqué, déjà anonymisés sur les
épreuves, ne reviennent donc pas par ce chemin.
"""
from collections import Counter
from collections.abc import Set
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.core.athlete_identity import athlete_identity_keys
from app.models.challenge import Challenge
from app.models.participation import Participation
from app.repositories import challenge_repository
from app.scrapers.base import ScrapedResult
from app.scrapers.utils import heat_is_challenge
from app.services import mapping

MIN_COVERAGE = 0.9
MIN_COURSES_PER_ATHLETE = 2
MIN_LINK_SHARE = 0.5


@dataclass(frozen=True)
class ChallengeRow:
    nom: str
    prenom: str
    bib_number: str | None
    rank_overall: int | None
    rank_gender: int | None
    rank_category: int | None
    total_time: str | None
    status: str
    raw_data: dict | None

    @classmethod
    def from_scraped(cls, scraped: ScrapedResult) -> "ChallengeRow":
        return cls(
            nom=scraped.athlete_name, prenom=scraped.athlete_firstname,
            bib_number=scraped.bib_number or None, rank_overall=scraped.rank_overall,
            rank_gender=scraped.rank_gender, rank_category=scraped.rank_category,
            total_time=mapping.total_time(scraped), status=mapping.derive_status(scraped),
            raw_data=scraped.raw_data or None,
        )

    @classmethod
    def from_participation(cls, participation: Participation) -> "ChallengeRow":
        return cls(
            nom=participation.athlete.nom, prenom=participation.athlete.prenom,
            bib_number=participation.bib_number, rank_overall=participation.rank_overall,
            rank_gender=participation.rank_gender, rank_category=participation.rank_category,
            total_time=participation.total_time, status=participation.status,
            raw_data=participation.raw_data,
        )


@dataclass(frozen=True)
class ChallengeMatch:
    #: Index de la ligne dans `rows` vers l'athlète apparié.
    athlete_ids: dict[int, int] = field(default_factory=dict)
    course_ids: list[int] = field(default_factory=list)


def _key(nom: str | None, prenom: str | None) -> str | None:
    """Clé d'identité normalisée (#907), au format de `Participation.source_identity_key`."""
    last_name_key, first_name_key = athlete_identity_keys(nom, prenom)
    return None if last_name_key is None else f"{last_name_key}|{first_name_key}"


def match(
    db: Session,
    rows: list[ChallengeRow],
    *,
    event_date: date | None,
    exclude_course_ids: Set[int] = frozenset(),
) -> ChallengeMatch | None:
    if not rows or event_date is None:
        return None
    # Deux clés par résultat : la graphie de la ligne source (#896), qui suit le
    # chronométreur même après un renommage de la fiche, et celle de la fiche.
    by_key: dict[str, dict[int, set[int]]] = {}
    for athlete_id, source_key, last_name_key, first_name_key, course_id, course_name in (
        challenge_repository.athletes_on_date(db, event_date)
    ):
        if course_id in exclude_course_ids or heat_is_challenge(course_name):
            continue
        record_key = None if last_name_key is None else f"{last_name_key}|{first_name_key}"
        for key in {source_key, record_key} - {None}:
            by_key.setdefault(key, {}).setdefault(athlete_id, set()).add(course_id)

    athlete_ids: dict[int, int] = {}
    per_course: Counter[int] = Counter()
    covered = 0
    for index, row in enumerate(rows):
        # Klikego publie « PRÉNOM NOM » en majuscules : l'ordre inverse est un second essai.
        candidates = by_key.get(_key(row.nom, row.prenom)) or by_key.get(_key(row.prenom, row.nom))
        if not candidates or len(candidates) != 1:
            continue
        ((athlete_id, course_ids),) = candidates.items()
        # Deux lignes vers une même fiche : la seconde est un homonyme qu'on ne sait pas placer.
        if athlete_id in athlete_ids.values():
            continue
        athlete_ids[index] = athlete_id
        per_course.update(course_ids)
        if len(course_ids) >= MIN_COURSES_PER_ATHLETE:
            covered += 1
    if covered < MIN_COVERAGE * len(rows):
        return None
    linked = sorted(
        course_id for course_id, count in per_course.items() if count >= MIN_LINK_SHARE * len(rows)
    )
    if len(linked) < MIN_COURSES_PER_ATHLETE:
        return None
    return ChallengeMatch(athlete_ids=athlete_ids, course_ids=linked)


def save(
    db: Session,
    *,
    name: str,
    event_date: date,
    source_url: str,
    rows: list[ChallengeRow],
    found: ChallengeMatch,
) -> Challenge:
    challenge = challenge_repository.upsert(db, name=name, event_date=event_date, source_url=source_url)
    challenge_repository.replace_links(db, challenge, found.course_ids)
    kept: list[int] = []
    for index, athlete_id in found.athlete_ids.items():
        row = rows[index]
        kept.append(challenge_repository.upsert_result(
            db, challenge, athlete_id=athlete_id, bib_number=row.bib_number,
            rank_overall=row.rank_overall, rank_gender=row.rank_gender,
            rank_category=row.rank_category, total_time=row.total_time,
            status=row.status, raw_data=row.raw_data,
        ).id)
    challenge_repository.delete_results_except(db, challenge, kept)
    db.refresh(challenge)
    return challenge


def _courses(challenge: Challenge) -> list[dict]:
    return sorted(
        ({"id": link.course.id, "name": link.course.name} for link in challenge.links),
        key=lambda course: course["name"],
    )


def for_athlete(db: Session, athlete_id: int) -> list[dict]:
    rows = challenge_repository.list_for_athlete(db, athlete_id)
    counts = challenge_repository.ranked_counts(db, [row.challenge_id for row in rows])
    return [
        {
            "id": row.challenge.id, "name": row.challenge.name,
            "event_date": row.challenge.event_date, "rank_overall": row.rank_overall,
            "ranked_count": counts.get(row.challenge_id, 0), "total_time": row.total_time,
            "courses": _courses(row.challenge),
        }
        for row in rows
    ]


def for_course(db: Session, course_id: int) -> list[dict]:
    challenges = challenge_repository.list_for_course(db, course_id)
    counts = challenge_repository.ranked_counts(db, [c.id for c in challenges])
    return [{"id": c.id, "name": c.name, "ranked_count": counts.get(c.id, 0)} for c in challenges]


def detail(db: Session, challenge_id: int) -> dict | None:
    challenge = challenge_repository.get(db, challenge_id)
    if challenge is None:
        return None
    results = sorted(
        challenge.results,
        key=lambda r: (r.rank_overall is None, r.rank_overall or 0, r.athlete.nom),
    )
    return {
        "id": challenge.id, "name": challenge.name, "event_date": challenge.event_date,
        "courses": _courses(challenge),
        "results": [
            {
                "athlete_id": r.athlete_id, "nom": r.athlete.nom, "prenom": r.athlete.prenom,
                "rank_overall": r.rank_overall, "total_time": r.total_time, "status": r.status,
            }
            for r in results
        ],
    }
