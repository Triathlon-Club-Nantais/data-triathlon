"""Accès données pour VolunteerAction — seule couche qui touche la Session (Principe II).

Deux fonctions : `create` consigne une déclaration, `list_for_athlete_season`
et `exists_for_athlete_season` la relisent. Pas de suppression ni de mise à
jour — un journal (research.md D4), sur le patron d'`AdminActionLog`.
"""
from sqlalchemy.orm import Session

from app.models.volunteer_action import VolunteerAction


def create(db: Session, *, athlete_id: int, season: int, declared_by_user_id: int) -> VolunteerAction:
    action = VolunteerAction(
        athlete_id=athlete_id, season=season, declared_by_user_id=declared_by_user_id
    )
    db.add(action)
    db.flush()
    return action


def list_for_athlete_season(db: Session, *, athlete_id: int, season: int) -> list[VolunteerAction]:
    return (
        db.query(VolunteerAction)
        .filter(VolunteerAction.athlete_id == athlete_id, VolunteerAction.season == season)
        .order_by(VolunteerAction.created_at.desc())
        .all()
    )


def exists_for_athlete_season(db: Session, *, athlete_id: int, season: int) -> bool:
    return (
        db.query(VolunteerAction.id)
        .filter(VolunteerAction.athlete_id == athlete_id, VolunteerAction.season == season)
        .first()
        is not None
    )
