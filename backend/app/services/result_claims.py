"""Réclamer un résultat rangé sur une autre fiche (#1637).

Un compte rattaché (#1325) dit « ce résultat est à moi » pour un résultat
validé et individuel d'une autre fiche, typiquement celle d'un homonyme. Jamais
d'office : un responsable valide, et la validation passe par le geste existant
`admin_actions.reassign_participation` (résultat figé contre l'import, fiche
d'origine purgée si elle se vide, journal). La file est celle des rattachements
de fiche (`/admin/rattachements`), en section distincte.
"""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.core.season import season_of
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.club_member import ClubMember
from app.models.participation import Participation
from app.models.result_claim import STATUS_PENDING, ResultClaim
from app.models.user import User
from app.repositories import (
    athlete_repository,
    club_member_repository,
    participation_repository,
    result_claim_repository,
)
from app.services import admin_actions, audit

logger = logging.getLogger(__name__)

MAX_PENDING = 5
_ENTITY = "participation"


class NoClaimedAthleteError(DomainError):
    status_code = 409
    message = "Rattachez d'abord votre fiche athlète (« C'est moi » sur votre fiche) pour réclamer un résultat."


class UnclaimableResultError(DomainError):
    status_code = 409
    message = "Ce résultat ne peut pas être réclamé : il est déjà sur votre fiche, en attente de validation, ou d'un relais."


class TooManyClaimsError(DomainError):
    status_code = 409
    message = f"Vous avez déjà {MAX_PENDING} réclamations en attente : attendez la réponse du club."


def _claim_not_pending() -> NotFoundError:
    return NotFoundError("Cette réclamation n'est plus en attente.")


def request_claim(db: Session, user: User, participation_id: int) -> ResultClaim:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    participation = participation_repository.get(db, participation_id)
    if participation is None:
        raise NotFoundError("Résultat introuvable.")
    if participation.athlete_id == user.athlete_id or participation.is_pending_validation or participation.is_relay:
        raise UnclaimableResultError()
    existing = result_claim_repository.get_for_participation(db, user.id, participation_id)
    if existing is not None and existing.status == STATUS_PENDING:
        return existing  # un second clic ne la renvoie pas en fin de file
    if result_claim_repository.count_pending_for_user(db, user.id) >= MAX_PENDING:
        raise TooManyClaimsError()
    claim = result_claim_repository.replace_pending(db, user_id=user.id, participation_id=participation_id)
    logger.info("Result claim requested: user=%s participation=%s", user.id, participation_id)
    return claim


def cancel_claim(db: Session, user: User, claim_id: int) -> None:
    claim = result_claim_repository.get_for_user(db, user.id, claim_id)
    if claim is None:
        raise NotFoundError("Réclamation introuvable.")
    result_claim_repository.delete_claim(db, claim)


def list_mine(db: Session, user: User) -> list[ResultClaim]:
    return result_claim_repository.list_for_user(db, user.id)


def approve(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = result_claim_repository.get_pending(db, claim_id)
    if claim is None or claim.user.athlete_id is None:
        raise _claim_not_pending()
    participation_id, user_id, target = claim.participation_id, claim.user_id, claim.user.athlete_id
    # Le geste du back-office : verrou de l'épreuve, conflit si la fiche du compte
    # y a déjà un résultat, figement contre l'import, purge de la fiche vidée.
    admin_actions.reassign_participation(db, participation_id=participation_id, athlete_id=target, user_id=actor_id)
    result_claim_repository.delete_claim(db, claim)
    audit.record(
        db, actor_id, action="result_claim.approve", entity_type=_ENTITY, entity_id=participation_id,
        payload={"user_id": user_id, "athlete_id": target, "claim_id": claim_id},
    )


def reject(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = result_claim_repository.get_pending(db, claim_id)
    if claim is None:
        raise _claim_not_pending()
    result_claim_repository.reject(db, claim, now=utcnow())
    audit.record(
        db, actor_id, action="result_claim.reject", entity_type=_ENTITY, entity_id=claim.participation_id,
        payload={"user_id": claim.user_id, "claim_id": claim_id},
    )


@dataclass(frozen=True)
class ResultClaimReview:
    """Une réclamation de la file et ce qui aide à la juger."""

    claim: ResultClaim
    user: User
    participation: Participation
    current_athlete: Athlete
    #: Résultats de la fiche actuelle, celui-ci compris : 1 veut dire qu'elle sera purgée.
    current_athlete_results: int
    claimant_athlete: Athlete | None
    claimant_licensee: ClubMember | None


def list_pending_with_hints(db: Session, today: date) -> list[ResultClaimReview]:
    claims = result_claim_repository.list_pending(db)
    claimant_ids = [claim.user.athlete_id for claim in claims if claim.user.athlete_id is not None]
    claimants = athlete_repository.get_many(db, claimant_ids)
    licensees = club_member_repository.linked_by_athlete(db, season_of(today), claimant_ids)
    return [
        ResultClaimReview(
            claim=claim,
            user=claim.user,
            participation=claim.participation,
            current_athlete=claim.participation.athlete,
            current_athlete_results=participation_repository.count_for_athlete(db, claim.participation.athlete_id),
            claimant_athlete=claimants.get(claim.user.athlete_id),
            claimant_licensee=licensees.get(claim.user.athlete_id),
        )
        for claim in claims
    ]
