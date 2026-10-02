"""Accès données pour SeasonValidation — seule couche qui touche la Session (Principe II).

L'existence de la ligne porte le statut (research.md D5) : `create` valide,
`delete` dévalide. `map_by_athlete` sert la lecture en masse de
`athlete_repository.list_with_season_participation_count`.
"""
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.season_validation import SeasonValidation


def create(
    db: Session, *, athlete_id: int, season: int, validated_by_user_id: int
) -> SeasonValidation:
    validation = SeasonValidation(
        athlete_id=athlete_id, season=season, validated_by_user_id=validated_by_user_id
    )
    db.add(validation)
    db.flush()
    return validation


def get_for_athlete_season(db: Session, *, athlete_id: int, season: int) -> SeasonValidation | None:
    return (
        db.query(SeasonValidation)
        .filter(SeasonValidation.athlete_id == athlete_id, SeasonValidation.season == season)
        .first()
    )


def delete(db: Session, validation: SeasonValidation) -> None:
    db.delete(validation)
    db.flush()


def map_by_athlete(db: Session, *, athlete_ids: list[int], season: int) -> dict[int, bool]:
    """`{athlete_id: True}` pour chaque athlète validé sur `season`, parmi `athlete_ids`.

    Absent de la carte = non validé — l'appelant lit `carte.get(id, False)`.
    """
    if not athlete_ids:
        return {}
    lignes = (
        db.query(SeasonValidation.athlete_id)
        .filter(SeasonValidation.athlete_id.in_(athlete_ids), SeasonValidation.season == season)
        .all()
    )
    return {athlete_id: True for (athlete_id,) in lignes}


def repoint_deduplicated(db: Session, *, from_athlete_id: int, to_athlete_id: int) -> int:
    """Repointe les validations d'une fiche absorbée par une fusion (#908).

    Une saison validée des deux côtés garde la validation de la fiche conservée :
    `uq_season_validation_athlete_season` n'en admet qu'une, et l'existence de la
    ligne porte seule le statut. Rend le nombre de saisons validées reprises.
    """
    kept_seasons = select(SeasonValidation.season).where(SeasonValidation.athlete_id == to_athlete_id)
    db.execute(
        sql_delete(SeasonValidation).where(
            SeasonValidation.athlete_id == from_athlete_id, SeasonValidation.season.in_(kept_seasons)
        )
    )
    return db.execute(
        update(SeasonValidation)
        .where(SeasonValidation.athlete_id == from_athlete_id)
        .values(athlete_id=to_athlete_id)
    ).rowcount


def count_for_athlete(db: Session, athlete_id: int) -> int:
    return db.scalar(select(func.count()).select_from(SeasonValidation).where(SeasonValidation.athlete_id == athlete_id))


def delete_for_athlete(db: Session, athlete_id: int) -> int:
    return db.query(SeasonValidation).filter(SeasonValidation.athlete_id == athlete_id).delete()
