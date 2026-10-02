"""Accès données pour IgnoredAthletePair (#908). L'existence de la ligne porte la décision."""
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.ignored_athlete_pair import IgnoredAthletePair


def normalized(athlete_id_a: int, athlete_id_b: int) -> tuple[int, int]:
    return (athlete_id_a, athlete_id_b) if athlete_id_a < athlete_id_b else (athlete_id_b, athlete_id_a)


def create(db: Session, *, athlete_id_a: int, athlete_id_b: int, user_id: int) -> IgnoredAthletePair:
    low, high = normalized(athlete_id_a, athlete_id_b)
    ignored = IgnoredAthletePair(athlete_id_low=low, athlete_id_high=high, ignored_by_user_id=user_id)
    db.add(ignored)
    db.flush()
    return ignored


def exists(db: Session, *, athlete_id_a: int, athlete_id_b: int) -> bool:
    low, high = normalized(athlete_id_a, athlete_id_b)
    return db.scalar(
        select(IgnoredAthletePair.id).where(
            IgnoredAthletePair.athlete_id_low == low, IgnoredAthletePair.athlete_id_high == high
        )
    ) is not None


def all_pairs(db: Session) -> set[tuple[int, int]]:
    return set(db.execute(select(IgnoredAthletePair.athlete_id_low, IgnoredAthletePair.athlete_id_high)).tuples())


def repoint(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Reporte sur la fiche conservée les paires écartées de la fiche absorbée par une
    fusion : le jugement « deux personnes » vaut pour la personne, pas pour la ligne.
    La paire des deux fiches fusionnées tombe, un doublon de paire aussi ; auteur et
    date d'origine sont gardés. Rend le nombre de paires reportées."""
    pairs = db.scalars(
        select(IgnoredAthletePair).where(or_(
            IgnoredAthletePair.athlete_id_low == from_athlete_id,
            IgnoredAthletePair.athlete_id_high == from_athlete_id,
        ))
    ).all()
    moved = 0
    for pair in pairs:
        other = pair.athlete_id_high if pair.athlete_id_low == from_athlete_id else pair.athlete_id_low
        db.delete(pair)
        db.flush()
        if other == to_athlete_id or exists(db, athlete_id_a=to_athlete_id, athlete_id_b=other):
            continue
        low, high = normalized(to_athlete_id, other)
        db.add(IgnoredAthletePair(athlete_id_low=low, athlete_id_high=high,
                                  ignored_by_user_id=pair.ignored_by_user_id, ignored_at=pair.ignored_at))
        db.flush()
        moved += 1
    return moved
