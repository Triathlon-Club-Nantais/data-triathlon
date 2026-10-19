"""Rattachement d'un compte à sa fiche athlète (#1325).

Jamais d'office : la liste d'adresses d'adhérents ne porte que des adresses, sans
nom, et validerait le rattachement de n'importe quelle fiche. Toute demande passe
par la file du back-office, où la liste n'est qu'un indice parmi d'autres.
Le rattachement validé vit sur `users.athlete_id` ; il rend le compte adhérent
(`membership.is_member`).
"""
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.core.season import season_of
from app.core.time import utcnow
from app.models.athlete import Athlete
from app.models.athlete_claim import AthleteClaim
from app.models.club_member import ClubMember
from app.models.user import User
from app.repositories import (
    athlete_claim_repository,
    athlete_repository,
    club_member_repository,
    member_email_repository,
    user_repository,
)
from app.services import audit

logger = logging.getLogger(__name__)

_ENTITY = "user"


class AlreadyLinkedError(DomainError):
    status_code = 409
    message = "Votre compte est déjà rattaché à une fiche : détachez-vous d'abord."


def _claim_not_pending() -> NotFoundError:
    return NotFoundError("Cette demande n'est plus en attente.")


def session_view(db: Session, user: User) -> tuple[Athlete | None, AthleteClaim | None]:
    """La fiche rattachée et la demande en cours, pour `/auth/me`."""
    athlete = athlete_repository.get(db, user.athlete_id) if user.athlete_id is not None else None
    return athlete, athlete_claim_repository.get_for_user(db, user.id)


def request_claim(db: Session, user: User, athlete_id: int) -> AthleteClaim:
    if user.athlete_id is not None:
        raise AlreadyLinkedError()
    if athlete_repository.get(db, athlete_id) is None:
        raise NotFoundError("Fiche athlète introuvable.")
    claim = athlete_claim_repository.replace_pending(db, user_id=user.id, athlete_id=athlete_id)
    logger.info("Athlete claim requested: user=%s athlete=%s", user.id, athlete_id)
    return claim


def cancel_claim(db: Session, user: User) -> None:
    athlete_claim_repository.delete_for_user(db, user.id)


def detach(db: Session, user: User) -> None:
    if user.athlete_id is None:
        return
    logger.info("Athlete detached: user=%s athlete=%s", user.id, user.athlete_id)
    user_repository.set_athlete(db, user, None)


def approve(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = athlete_claim_repository.get_pending(db, claim_id)
    if claim is None:
        raise _claim_not_pending()
    user, athlete_id = claim.user, claim.athlete_id
    user_repository.set_athlete(db, user, athlete_id)
    athlete_claim_repository.delete_claim(db, claim)
    audit.record(
        db, actor_id, action="athlete_claim.approve", entity_type=_ENTITY, entity_id=user.id,
        payload={"athlete_id": athlete_id, "claim_id": claim_id},
    )


def reject(db: Session, claim_id: int, *, actor_id: int) -> None:
    claim = athlete_claim_repository.get_pending(db, claim_id)
    if claim is None:
        raise _claim_not_pending()
    athlete_claim_repository.reject(db, claim, now=utcnow())
    audit.record(
        db, actor_id, action="athlete_claim.reject", entity_type=_ENTITY, entity_id=claim.user_id,
        payload={"athlete_id": claim.athlete_id, "claim_id": claim_id},
    )


def admin_detach(db: Session, user_id: int, *, actor_id: int) -> None:
    """Le club détache un compte de sa fiche (#1633), par exemple au départ d'un adhérent."""
    user = user_repository.get(db, user_id)
    if user is None or user.athlete_id is None:
        raise NotFoundError("Ce compte n'est rattaché à aucune fiche.")
    athlete_id = user.athlete_id
    user_repository.set_athlete(db, user, None)
    audit.record(
        db, actor_id, action="athlete_claim.detach", entity_type=_ENTITY, entity_id=user_id,
        payload={"athlete_id": athlete_id},
    )


@dataclass(frozen=True)
class AthleteLink:
    user: User
    athlete: Athlete
    #: La fiche est licenciée au club cette saison : le rattachement vaut adhésion (#1633).
    licensed_this_season: bool


def list_links(db: Session, today: date) -> list[AthleteLink]:
    """Les comptes rattachés, ceux dont la licence ne court plus d'abord."""
    users = user_repository.list_linked(db)
    athlete_ids = [user.athlete_id for user in users]
    athletes = athlete_repository.get_many(db, athlete_ids)
    licensed = club_member_repository.linked_by_athlete(
        db, club_member_repository.counting_season(db, season_of(today)), athlete_ids
    )
    links = [
        AthleteLink(user=user, athlete=athletes[user.athlete_id], licensed_this_season=user.athlete_id in licensed)
        for user in users
        if user.athlete_id in athletes
    ]
    return sorted(links, key=lambda link: (link.licensed_this_season, link.user.id))


@dataclass(frozen=True)
class ClaimReview:
    """Une demande en attente et ce qui aide à la juger, d'un seul coup d'œil."""

    claim: AthleteClaim
    user: User
    athlete: Athlete
    licensee: ClubMember | None
    email_on_member_list: bool
    linked_accounts: int


def list_pending_with_hints(db: Session, today: date) -> list[ClaimReview]:
    claims = athlete_claim_repository.list_pending(db)
    athlete_ids = [claim.athlete_id for claim in claims]
    licensees = club_member_repository.linked_by_athlete(db, season_of(today), athlete_ids)
    on_list = member_email_repository.counting_among(db, [claim.user.email for claim in claims], today)
    linked = user_repository.count_linked_by_athlete(db, athlete_ids)
    return [
        ClaimReview(
            claim=claim,
            user=claim.user,
            athlete=claim.athlete,
            licensee=licensees.get(claim.athlete_id),
            email_on_member_list=member_email_repository.normalize(claim.user.email) in on_list,
            linked_accounts=linked.get(claim.athlete_id, 0),
        )
        for claim in claims
    ]
