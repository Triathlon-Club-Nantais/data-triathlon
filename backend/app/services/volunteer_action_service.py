"""Logique métier du formulaire public de déclaration de bénévolat (#778) et
de son workflow de validation admin (#779)."""
from sqlalchemy.orm import Session

from app.core import season as season_module
from app.core.exceptions import NotFoundError
from app.models.volunteer_action import VolunteerAction
from app.repositories import (
    admin_action_log_repository,
    athlete_repository,
    volunteer_action_repository,
)


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


def list_pending(db: Session) -> list[VolunteerAction]:
    """File d'attente admin (#779 FR-001)."""
    return volunteer_action_repository.list_pending(db)


def list_validated_for_athlete(db: Session, *, athlete_id: int) -> list[VolunteerAction]:
    """Fiche athlète (#781 FR-001/FR-002/FR-004)."""
    return volunteer_action_repository.list_validated_for_athlete(db, athlete_id=athlete_id)


def _action_ou_404(db: Session, action_id: int) -> VolunteerAction:
    action = volunteer_action_repository.get(db, action_id)
    if action is None:
        raise NotFoundError("Déclaration introuvable.")
    return action


def accept(db: Session, *, admin_user_id: int, action_id: int) -> VolunteerAction:
    """Fait passer une déclaration « en attente » à « validée » (FR-003).

    No-op pour tout autre statut de départ — déjà « validée » (FR-004) ou
    « refusée » (#779, research.md D6/`/speckit-analyze` finding U1) —,
    jamais d'erreur ni de transition."""
    action = _action_ou_404(db, action_id)
    if action.status != "en_attente":
        return action

    mise_a_jour = volunteer_action_repository.set_status(db, action_id, "validee")
    admin_action_log_repository.create(
        db,
        user_id=admin_user_id,
        action="athlete.volunteer_action.accept",
        entity_type="athlete",
        entity_id=action.athlete_id,
        payload={"season": action.season, "action_id": action_id},
    )
    return mise_a_jour


def reject(db: Session, *, admin_user_id: int, action_id: int) -> VolunteerAction:
    """Fait passer une déclaration « en attente » ou « validée » à
    « refusée » (FR-005, research.md D6) ; idempotent si déjà « refusée »
    (FR-006)."""
    action = _action_ou_404(db, action_id)
    if action.status == "refusee":
        return action

    mise_a_jour = volunteer_action_repository.set_status(db, action_id, "refusee")
    admin_action_log_repository.create(
        db,
        user_id=admin_user_id,
        action="athlete.volunteer_action.reject",
        entity_type="athlete",
        entity_id=action.athlete_id,
        payload={"season": action.season, "action_id": action_id},
    )
    return mise_a_jour
