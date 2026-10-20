"""Coéquipiers de course (#1701) : membres du club les plus croisés sur mes épreuves."""
from sqlalchemy.orm import Session

from app.core.identity import identity_hash
from app.repositories import opposition_repository, participation_repository

LIMIT = 3


def list_for_athlete(db: Session, *, athlete_id: int, federal_only: bool, seasons: list[int] | None) -> list[dict]:
    rows = participation_repository.teammate_rows(db, athlete_id=athlete_id, federal_only=federal_only, seasons=seasons)
    opposed = opposition_repository.all_hashes(db)
    kept = [r for r in rows if identity_hash(r.nom, r.prenom) not in opposed]
    kept.sort(key=lambda r: (-r[3], r.nom, r.prenom, r.id))
    return [
        {"athlete_id": r.id, "prenom": r.prenom, "nom": r.nom, "courses_communes": r[3]} for r in kept[:LIMIT]
    ]
