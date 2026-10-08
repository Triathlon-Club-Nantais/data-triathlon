"""Accès données pour IgnoredIdentityCase (#1252)."""
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.ignored_identity_case import IgnoredIdentityCase


def find(db: Session, *, athlete_id: int, reason: str) -> IgnoredIdentityCase | None:
    return db.scalar(
        select(IgnoredIdentityCase).where(
            IgnoredIdentityCase.athlete_id == athlete_id, IgnoredIdentityCase.reason == reason
        )
    )


def save(db: Session, *, athlete_id: int, reason: str, fingerprint: str, user_id: int) -> IgnoredIdentityCase:
    """Pose la décision, ou la renouvelle sur des données qui ont changé depuis."""
    case = find(db, athlete_id=athlete_id, reason=reason)
    if case is None:
        case = IgnoredIdentityCase(athlete_id=athlete_id, reason=reason)
        db.add(case)
    case.fingerprint = fingerprint
    case.ignored_by_user_id = user_id
    case.ignored_at = utcnow()
    db.flush()
    return case


def get(db: Session, case_id: int) -> IgnoredIdentityCase | None:
    return db.get(IgnoredIdentityCase, case_id)


def delete(db: Session, case: IgnoredIdentityCase) -> None:
    db.delete(case)
    db.flush()


def delete_for_athlete(db: Session, athlete_id: int) -> None:
    db.execute(sql_delete(IgnoredIdentityCase).where(IgnoredIdentityCase.athlete_id == athlete_id))


def fingerprints(db: Session, reason: str) -> dict[int, str]:
    return dict(
        db.execute(
            select(IgnoredIdentityCase.athlete_id, IgnoredIdentityCase.fingerprint)
            .where(IgnoredIdentityCase.reason == reason)
        ).tuples().all()
    )


def list_with_athletes(db: Session) -> list[tuple[IgnoredIdentityCase, Athlete]]:
    """Les cas écartés et leur fiche, le plus récent d'abord."""
    return [
        tuple(row)
        for row in db.execute(
            select(IgnoredIdentityCase, Athlete)
            .join(Athlete, Athlete.id == IgnoredIdentityCase.athlete_id)
            .order_by(IgnoredIdentityCase.ignored_at.desc(), IgnoredIdentityCase.id.desc())
        )
    ]
