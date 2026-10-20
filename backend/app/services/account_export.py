"""Export des données du compte connecté (#1674), droit d'accès et de portabilité."""
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories import (
    athlete_repository,
    feedback_repository,
    participation_repository,
    volunteer_action_repository,
)
from app.schemas.account_export import AccountExport, ExportedResultClaim, ExportedVolunteerAction
from app.schemas.auth import AccountIdentityRead
from app.services.auth.idp import registry


def identities_of(user: User) -> list[AccountIdentityRead]:
    """Les moyens de connexion du compte, du plus ancien au plus récent ; jamais le `subject` ni le secret."""
    return [
        AccountIdentityRead(
            provider=identity.provider,
            label=provider.label if (provider := registry.get(identity.provider)) else identity.provider,
            email=identity.email,
            created_at=identity.created_at,
        )
        for identity in sorted(user.identities, key=lambda identity: identity.created_at)
    ]


def build(db: Session, user: User) -> AccountExport:
    athlete_id = user.athlete_id
    return AccountExport.model_validate({
        "account": user,
        "identities": identities_of(user),
        "athlete": athlete_repository.get(db, athlete_id) if athlete_id else None,
        "athlete_claim": user.athlete_claim,
        "result_claims": [
            ExportedResultClaim(
                participation_id=claim.participation_id, status=claim.status, created_at=claim.created_at,
                course_name=claim.participation.course.name, event_date=claim.participation.course.event_date,
                total_time=claim.participation.total_time,
            )
            for claim in user.result_claims
        ],
        "season_goals": sorted(user.season_goals, key=lambda goal: (goal.season, goal.created_at)),
        "volunteer_actions": [
            ExportedVolunteerAction(
                season=action.season, title=action.title, description=action.description, status=action.status,
                created_at=action.created_at, for_my_athlete=action.athlete_id == athlete_id,
            )
            for action in volunteer_action_repository.list_for_account(db, user_id=user.id, athlete_id=athlete_id)
        ],
        "feedback": feedback_repository.list_for_user(db, user.id),
        # En attente et refusés compris : ce sont aussi ses données.
        "results": participation_repository.list_for_athlete(db, athlete_id, include_pending=True) if athlete_id else [],
    }, from_attributes=True)
