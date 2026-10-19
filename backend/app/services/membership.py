"""Derived member status (#1322).

Never stored on `users` (invariant of #115, discussion #209): evaluated on each
request, so removing an address from the member list takes effect on the next
request without revoking any session.
"""
from datetime import date

from sqlalchemy.orm import Session

from app.core.season import season_of
from app.models.user import SYSTEM_USER_EMAIL, User
from app.repositories import (
    allowed_email_repository,
    club_member_repository,
    member_email_repository,
)
from app.services.auth.idp.base import ExternalIdentity


def is_member(db: Session, user: User | None, today: date) -> bool:
    if user is None or not user.is_active or user.email == SYSTEM_USER_EMAIL:
        return False
    # Un rattachement validé (#1325) ne vaut reconnaissance que si la fiche est
    # licenciée au club pour la saison (#1633) : il s'éteint seul au renouvellement.
    if user.athlete_id is not None and club_member_repository.is_linked_licensee(
        db, user.athlete_id, club_member_repository.counting_season(db, season_of(today))
    ):
        return True
    return member_email_repository.counts(db, user.email, today)


def retained_email(db: Session, identity: ExternalIdentity, today: date) -> str:
    """Address kept on the account among the certified ones (FR-016): the first
    on the allow-list, else the first counting on the member list, else the
    primary. The allow-list wins because it carries the day-one role."""
    candidates = [email for email in dict.fromkeys((identity.email, *identity.verified_emails)) if email]
    for email in candidates:
        if allowed_email_repository.exists(db, email):
            return email
    for email in candidates:
        if member_email_repository.counts(db, email, today):
            return email
    return identity.email
