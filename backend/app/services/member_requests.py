"""Demande d'adhésion d'un compte connecté qui n'est pas reconnu adhérent (#1785).

La demande ne rend jamais adhérent d'office : le club la valide dans sa file, et
la validation inscrit l'adresse du compte sur la liste de la saison.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.core.season import current_season
from app.core.time import utcnow
from app.models.member_request import STATUS_REJECTED, MemberRequest
from app.models.user import User
from app.repositories import member_request_repository
from app.schemas.member_request import MemberRequestCreate
from app.services import audit, member_emails_service, membership, profile_service
from app.services.member_emails_service import AlreadyListedError

logger = logging.getLogger(__name__)

REQUEST_AGAIN_AFTER = timedelta(days=30)

_ENTITY = "user"


class AlreadyMemberError(DomainError):
    status_code = 409
    message = "Votre compte est déjà reconnu adhérent."


class RejectedRecentlyError(DomainError):
    status_code = 409

    def __init__(self, decided_at: datetime):
        again = (decided_at + REQUEST_AGAIN_AFTER).strftime("%d/%m/%Y")
        super().__init__(
            f"Votre demande a été refusée. Vous pourrez en envoyer une nouvelle à partir du {again}."
        )


def _not_pending() -> NotFoundError:
    return NotFoundError("Cette demande n'est plus en attente.")


def _organisation_id(db: Session) -> int:
    return profile_service.default_organisation_id(db)


def current_for(db: Session, user: User) -> MemberRequest | None:
    """Sans organisation, il n'y a pas de demande : les lectures ne lèvent rien."""
    return member_request_repository.get_for_user_in_default_organisation(db, user.id)


def request_membership(
    db: Session, user: User, data: MemberRequestCreate, *, now: datetime
) -> MemberRequest:
    if membership.is_member(db, user, now.date()):
        raise AlreadyMemberError()
    organisation_id = _organisation_id(db)
    previous = member_request_repository.get_for_user(db, user.id, organisation_id)
    if (
        previous is not None
        and previous.status == STATUS_REJECTED
        and previous.decided_at is not None
        and now.date() < (previous.decided_at + REQUEST_AGAIN_AFTER).date()
    ):
        raise RejectedRecentlyError(previous.decided_at)
    request = member_request_repository.upsert_pending(
        db,
        user_id=user.id,
        organisation_id=organisation_id,
        first_name=data.first_name,
        last_name=data.last_name,
        birth_date=data.birth_date,
        phone=data.phone,
    )
    logger.info("Member request submitted: user=%s", user.id)
    return request


def cancel_pending(db: Session, user: User) -> None:
    """Une demande refusée reste : la supprimer contournerait le délai avant une nouvelle."""
    member_request_repository.delete_pending_for_user(db, user.id, _organisation_id(db))


def list_pending(db: Session) -> list[MemberRequest]:
    return member_request_repository.list_pending(db, _organisation_id(db))


def count_pending(db: Session) -> int:
    return member_request_repository.count_pending(db, _organisation_id(db))


def approve(db: Session, request_id: int, *, actor_id: int) -> None:
    request = member_request_repository.get_pending(db, request_id)
    if request is None:
        raise _not_pending()
    user_id = request.user_id
    try:
        member_emails_service.add(
            db, email=request.user.email, season=current_season(), user_id=actor_id
        )
    except AlreadyListedError:
        pass  # l'adresse est devenue adhérente entre-temps : le but est atteint
    member_request_repository.delete_request(db, request)
    audit.record(
        db,
        actor_id,
        action="member_request.approve",
        entity_type=_ENTITY,
        entity_id=user_id,
        payload={"request_id": request_id},
    )


def reject(db: Session, request_id: int, *, actor_id: int) -> None:
    request = member_request_repository.get_pending(db, request_id)
    if request is None:
        raise _not_pending()
    member_request_repository.reject(db, request, now=utcnow())
    audit.record(
        db,
        actor_id,
        action="member_request.reject",
        entity_type=_ENTITY,
        entity_id=request.user_id,
        payload={"request_id": request_id},
    )
