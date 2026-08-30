"""Accès données pour SeasonValidation — seule couche qui touche la Session (Principe II).

L'existence de la ligne porte le statut (research.md D5) : `create` valide,
`delete` dévalide. `map_by_athlete` sert la lecture en masse de
`athlete_repository.list_with_season_participation_count`.
"""
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
