"""Accès données pour AthleteKnownClub (#1209). Ne commite jamais."""
from collections.abc import Collection

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.athlete_known_club import AthleteKnownClub


def add(db: Session, *, athlete_id: int, club_key: str, user_id: int | None) -> AthleteKnownClub:
    known = AthleteKnownClub(athlete_id=athlete_id, club_key=club_key, created_by_user_id=user_id)
    db.add(known)
    db.flush()
    return known


def exists(db: Session, *, athlete_id: int, club_key: str) -> bool:
    return db.scalar(
        select(AthleteKnownClub.id).where(
            AthleteKnownClub.athlete_id == athlete_id, AthleteKnownClub.club_key == club_key
        )
    ) is not None


def keys_by_athlete(db: Session, athlete_ids: Collection[int] | None = None) -> dict[int, set[str]]:
    """Clubs confirmés par fiche ; `None` lit toutes les fiches (revue d'identité)."""
    query = select(AthleteKnownClub.athlete_id, AthleteKnownClub.club_key)
    if athlete_ids is not None:
        if not athlete_ids:
            return {}
        query = query.where(AthleteKnownClub.athlete_id.in_(set(athlete_ids)))
    keys: dict[int, set[str]] = {}
    for athlete_id, club_key in db.execute(query):
        keys.setdefault(athlete_id, set()).add(club_key)
    return keys


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Reporte les clubs confirmés de la fiche absorbée par une fusion ; un club
    déjà confirmé sur la fiche conservée tombe. Rend le nombre de clubs reportés."""
    kept = keys_by_athlete(db, [to_athlete_id]).get(to_athlete_id, set())
    moved = 0
    for known in db.scalars(select(AthleteKnownClub).where(AthleteKnownClub.athlete_id == from_athlete_id)).all():
        if known.club_key in kept:
            db.delete(known)
        else:
            known.athlete_id = to_athlete_id
            moved += 1
    db.flush()
    return moved
