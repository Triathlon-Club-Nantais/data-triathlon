"""Accès données pour VolunteerAction — seule couche qui touche la Session (Principe II).

`create` (chemin admin, #709) et `create_pending` (formulaire self-service,
#778) consignent une déclaration. `set_status` (#779) est la seule mise à
jour — le statut, posé sans être jamais relu jusqu'ici, devient
significatif pour le workflow de validation admin. Pas de suppression.
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


def create_pending(
    db: Session,
    *,
    athlete_id: int,
    season: int,
    declared_by_user_id: int,
    title: str,
    description: str,
) -> VolunteerAction:
    """Formulaire public self-service (#778) — statut toujours « en attente »."""
    action = VolunteerAction(
        athlete_id=athlete_id,
        season=season,
        declared_by_user_id=declared_by_user_id,
        title=title,
        description=description,
        status="en_attente",
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
    """Le quota de saison (#779, FR-008) ne compte que les lignes validées —
    seul point de lecture, un seul appelant (`admin_actions.season_quota`)."""
    return (
        db.query(VolunteerAction.id)
        .filter(
            VolunteerAction.athlete_id == athlete_id,
            VolunteerAction.season == season,
            VolunteerAction.status == "validee",
        )
        .first()
        is not None
    )


def list_pending(db: Session) -> list[VolunteerAction]:
    """File d'attente admin (#779, FR-001) — tous athlètes confondus."""
    return (
        db.query(VolunteerAction)
        .filter(VolunteerAction.status == "en_attente")
        .order_by(VolunteerAction.created_at.desc())
        .all()
    )


def get(db: Session, action_id: int) -> VolunteerAction | None:
    return db.get(VolunteerAction, action_id)


def set_status(db: Session, action_id: int, status: str) -> VolunteerAction:
    action = db.get(VolunteerAction, action_id)
    action.status = status
    db.flush()
    return action
