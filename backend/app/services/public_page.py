"""Réglages de la fiche publique de l'athlète rattaché (#1692).

Possédés par le compte, jamais par la fiche : sans ligne, rien n'est masqué.
"""
from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.user import User
from app.repositories import (
    participation_repository,
    public_page_settings_repository,
    user_repository,
)
from app.schemas.public_page import PublicPageSettingsRead, PublicPageSettingsWrite

MAX_LINK_LENGTH = 200

#: Domaine accepté (lui-même ou un sous-domaine) et libellé affiché.
LINK_PROVIDERS = {
    "strava.com": "Strava",
    "garmin.com": "Garmin Connect",
    "polar.com": "Polar Flow",
    "suunto.com": "Suunto",
}


class NoClaimedAthleteError(DomainError):
    status_code = 409
    message = "Rattachez d'abord votre fiche athlète pour régler votre fiche publique."


class InvalidLinkError(DomainError):
    status_code = 422
    message = "Lien refusé : seuls les profils Strava, Garmin Connect, Polar Flow et Suunto en https sont acceptés."


class TooManyLinksError(DomainError):
    status_code = 422
    message = "Trois liens au plus, sans doublon."


class InvalidPinError(DomainError):
    status_code = 422
    message = "Ce résultat n'est pas sur votre fiche."


def _provider_domain(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        host, port = (parts.hostname or "").lower(), parts.port
    except ValueError:
        return None
    if parts.scheme != "https" or parts.username is not None or parts.password is not None or port is not None:
        return None
    return next((d for d in LINK_PROVIDERS if host == d or host.endswith("." + d)), None)


def normalize_link(url: str) -> str:
    url = url.strip()
    if len(url) > MAX_LINK_LENGTH or any(c.isspace() for c in url) or _provider_domain(url) is None:
        raise InvalidLinkError()
    return url


def link_label(url: str) -> str:
    return LINK_PROVIDERS[_provider_domain(url)]


def _read(db: Session, user: User, row) -> PublicPageSettingsRead:
    shared = len(user_repository.ids_linked_to_athlete(db, user.athlete_id)) > 1
    if row is None:
        return PublicPageSettingsRead(shared=shared)
    return PublicPageSettingsRead(
        hide_best_times=row.hide_best_times, hide_progression=row.hide_progression,
        hide_comparison=row.hide_comparison, links=list(row.links),
        pinned_participation_id=row.pinned_participation_id, shared=shared,
    )


def settings_of(db: Session, user: User) -> PublicPageSettingsRead:
    if user.athlete_id is None:
        return PublicPageSettingsRead()
    return _read(db, user, public_page_settings_repository.get(db, user.id))


def save(db: Session, user: User, data: PublicPageSettingsWrite) -> PublicPageSettingsRead:
    if user.athlete_id is None:
        raise NoClaimedAthleteError()
    links = [normalize_link(link) for link in data.links]
    if len(links) > 3 or len(set(links)) != len(links):
        raise TooManyLinksError()
    pin = data.pinned_participation_id
    if pin is not None and pin not in {
        p.id for p in participation_repository.list_for_athlete(db, user.athlete_id) if not p.is_pending_validation
    }:
        raise InvalidPinError()
    row = public_page_settings_repository.upsert(
        db, user.id, hide_best_times=data.hide_best_times, hide_progression=data.hide_progression,
        hide_comparison=data.hide_comparison, links=links, pinned_participation_id=pin,
    )
    return _read(db, user, row)
