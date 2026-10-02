"""Accès aux tables Challenge (#1008)."""
from collections.abc import Sequence
from datetime import date

from sqlalchemy import func, update
from sqlalchemy.orm import Session, selectinload

from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.challenge import Challenge, ChallengeCourse, ChallengeResult
from app.models.course import Course
from app.models.participation import Participation


def athletes_on_date(db: Session, event_date: date) -> list[tuple[int, str, str, int, str]]:
    """(athlete_id, nom, prenom, course_id, course_name) de chaque participation du jour."""
    return (
        db.query(Athlete.id, Athlete.nom, Athlete.prenom, Course.id, Course.name)
        .join(Participation, Participation.athlete_id == Athlete.id)
        .join(Course, Course.id == Participation.course_id)
        .filter(Course.event_date == event_date)
        .all()
    )


def upsert(db: Session, *, name: str, event_date: date, source_url: str) -> Challenge:
    challenge = (
        db.query(Challenge)
        .filter(Challenge.name == name, Challenge.event_date == event_date)
        .one_or_none()
    )
    if challenge is None:
        challenge = Challenge(name=name, event_date=event_date)
        db.add(challenge)
    challenge.source_url = source_url
    challenge.scraped_at = utcnow()
    db.flush()
    return challenge


def replace_links(db: Session, challenge: Challenge, course_ids: Sequence[int]) -> None:
    db.query(ChallengeCourse).filter(ChallengeCourse.challenge_id == challenge.id).delete(
        synchronize_session="fetch"
    )
    db.add_all(
        ChallengeCourse(challenge_id=challenge.id, course_id=course_id)
        for course_id in sorted(set(course_ids))
    )
    db.flush()


def upsert_result(db: Session, challenge: Challenge, **fields) -> ChallengeResult:
    query = db.query(ChallengeResult).filter(ChallengeResult.challenge_id == challenge.id)
    if fields.get("bib_number"):
        query = query.filter(ChallengeResult.bib_number == fields["bib_number"])
    else:
        query = query.filter(
            ChallengeResult.bib_number.is_(None),
            ChallengeResult.athlete_id == fields["athlete_id"],
        )
    row = query.one_or_none()
    if row is None:
        row = ChallengeResult(challenge_id=challenge.id)
        db.add(row)
    for key, value in fields.items():
        setattr(row, key, value)
    db.flush()
    return row


def get(db: Session, challenge_id: int) -> Challenge | None:
    return (
        db.query(Challenge)
        .options(
            selectinload(Challenge.results).selectinload(ChallengeResult.athlete),
            selectinload(Challenge.links).selectinload(ChallengeCourse.course),
        )
        .filter(Challenge.id == challenge_id)
        .one_or_none()
    )


def list_for_athlete(db: Session, athlete_id: int) -> list[ChallengeResult]:
    return (
        db.query(ChallengeResult)
        .join(Challenge, Challenge.id == ChallengeResult.challenge_id)
        .options(
            selectinload(ChallengeResult.challenge)
            .selectinload(Challenge.links)
            .selectinload(ChallengeCourse.course)
        )
        .filter(ChallengeResult.athlete_id == athlete_id)
        .order_by(Challenge.event_date.desc(), Challenge.id)
        .all()
    )


def list_for_athlete_ids(db: Session, athlete_id: int) -> list[ChallengeResult]:
    """Lignes à anonymiser ou à réattribuer (opposition, fusion), sans chargement annexe."""
    return db.query(ChallengeResult).filter(ChallengeResult.athlete_id == athlete_id).all()


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Repointe les lignes Challenge d'une fiche absorbée par une fusion (#908)."""
    return db.execute(
        update(ChallengeResult)
        .where(ChallengeResult.athlete_id == from_athlete_id)
        .values(athlete_id=to_athlete_id)
    ).rowcount


def list_for_course(db: Session, course_id: int) -> list[Challenge]:
    return (
        db.query(Challenge)
        .join(ChallengeCourse, ChallengeCourse.challenge_id == Challenge.id)
        .filter(ChallengeCourse.course_id == course_id)
        .order_by(Challenge.name)
        .all()
    )


def ranked_counts(db: Session, challenge_ids: Sequence[int]) -> dict[int, int]:
    if not challenge_ids:
        return {}
    rows = (
        db.query(ChallengeResult.challenge_id, func.count(ChallengeResult.id))
        .filter(
            ChallengeResult.challenge_id.in_(set(challenge_ids)),
            ChallengeResult.rank_overall.is_not(None),
        )
        .group_by(ChallengeResult.challenge_id)
        .all()
    )
    return {challenge_id: count for challenge_id, count in rows}


def delete_all(db: Session) -> int:
    db.query(ChallengeResult).delete(synchronize_session=False)
    db.query(ChallengeCourse).delete(synchronize_session=False)
    deleted = db.query(Challenge).delete(synchronize_session=False)
    db.flush()
    return deleted
