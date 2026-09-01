"""Logique métier du formulaire public de déclaration de bénévolat (#778)."""
from sqlalchemy.orm import Session

from app.core import season as season_module
from app.core.exceptions import NotFoundError
from app.models.volunteer_action import VolunteerAction
from app.repositories import athlete_repository, volunteer_action_repository


def create_pending(
    db: Session, *, declared_by_user_id: int, athlete_id: int, title: str, description: str
) -> VolunteerAction:
    """Un adhérent connecté crédite l'athlète de son choix pour la saison en
    cours, toujours à l'état « en attente » (FR-001 à FR-004, FR-009)."""
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Athlète introuvable.")

    return volunteer_action_repository.create_pending(
        db,
        athlete_id=athlete_id,
        season=season_module.current_season(),
        declared_by_user_id=declared_by_user_id,
        title=title,
        description=description,
    )
