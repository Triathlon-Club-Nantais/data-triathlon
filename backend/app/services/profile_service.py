"""Profils individuels génériques et leur journal de bord (#867, epic #863).

Réservé au côté jeunes pour cette itération par la seule garde d'accès
(`jeunes:read`/`jeunes:write`) posée sur `app/api/v1/admin_profiles.py` —
rien ici ne nomme « jeune » (research.md D1 de la feature).

Patron `app/services/auth/groups.py` : vues en dict, 404 explicite, journal
technique en anglais.
"""
import logging

from sqlalchemy.orm import Session

from app.core.exceptions import DomainError, NotFoundError
from app.models.personal_profile import PersonalProfile
from app.models.user import User
from app.repositories import profile_repository, role_repository

logger = logging.getLogger(__name__)


class NoOrganisationError(DomainError):
    """Patron `services/auth/authorization.NoOrganisationError` — aucune définition
    partagée entre les deux modules : chaque domaine RBAC porte la sienne,
    comme `GroupSlugTakenError`/`GroupInUseError` ne sont pas partagées non
    plus. Une base sans organisation ne devrait jamais se produire en
    exploitation (`tcn` est semée par migration) ; c'est un 422, pas un 500
    nu, le jour où une base de test ou de reprise en manque."""

    status_code = 422
    message = "Aucune organisation n'existe."


def _default_organisation_id(db: Session) -> int:
    organisation = role_repository.default_organisation(db)
    if organisation is None:
        raise NoOrganisationError()
    return organisation.id


def get_profile_or_404(db: Session, profile_id: int) -> PersonalProfile:
    profile = profile_repository.get(db, profile_id)
    if profile is None:
        raise NotFoundError("Ce profil n'existe pas.")
    return profile


def _log_entry_view(entry) -> dict:
    return {
        "id": entry.id,
        "entry_date": entry.entry_date,
        "text": entry.text,
        "created_by_name": entry.created_by.display_name if entry.created_by else None,
        "created_at": entry.created_at,
    }


def profile_view(profile: PersonalProfile) -> dict:
    """La forme rendue par la liste, `contracts/admin-profiles.md`."""
    return {
        "id": profile.id,
        "organisation_id": profile.organisation_id,
        "first_name": profile.first_name,
        "last_name": profile.last_name,
        "birth_date": profile.birth_date,
        "created_at": profile.created_at,
    }


def profile_detail_view(db: Session, profile: PersonalProfile) -> dict:
    """Le profil **et** son journal (FR-002 de spec.md)."""
    return profile_view(profile) | {
        "emergency_contact": profile.emergency_contact,
        "notes": profile.notes,
        "log_entries": [
            _log_entry_view(entry)
            for entry in profile_repository.list_log_entries(db, profile.id)
        ],
    }


def list_profiles(db: Session) -> list[PersonalProfile]:
    return profile_repository.list_all(db)


def create_profile(
    db: Session,
    actor: User,
    *,
    first_name: str,
    last_name: str,
    birth_date=None,
    emergency_contact: str = "",
    notes: str = "",
) -> PersonalProfile:
    profile = profile_repository.create(
        db,
        organisation_id=_default_organisation_id(db),
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        emergency_contact=emergency_contact,
        notes=notes,
        created_by_user_id=actor.id,
    )
    logger.info(
        "PersonalProfile created: actor=%s profile=%s", actor.id, profile.id
    )
    return profile


def update_profile(
    db: Session,
    actor: User,
    profile: PersonalProfile,
    *,
    first_name: str | None = None,
    last_name: str | None = None,
    birth_date=None,
    emergency_contact: str | None = None,
    notes: str | None = None,
) -> PersonalProfile:
    """Corrige les champs fournis. Patron `PATCH` partiel de `GroupUpdate` :
    un champ nullable (`birth_date`) omis à `None` ne peut pas être **effacé**
    par cette route — hors périmètre de #867, qui ne le demande pas."""
    champs = {
        champ: valeur
        for champ, valeur in {
            "first_name": first_name,
            "last_name": last_name,
            "birth_date": birth_date,
            "emergency_contact": emergency_contact,
            "notes": notes,
        }.items()
        if valeur is not None
    }
    profile_repository.update(db, profile, **champs)
    logger.info("PersonalProfile updated: actor=%s profile=%s", actor.id, profile.id)
    return profile


def add_log_entry(
    db: Session,
    actor: User,
    profile: PersonalProfile,
    *,
    text: str,
    entry_date=None,
) -> PersonalProfile:
    """Ajoute une entrée. Le journal conserve **tout** son historique
    (FR-006 de spec.md) — cette fonction ne remplace jamais rien."""
    profile_repository.add_log_entry(
        db,
        profile_id=profile.id,
        text=text,
        entry_date=entry_date,
        created_by_user_id=actor.id,
    )
    logger.info(
        "Profile log entry added: actor=%s profile=%s", actor.id, profile.id
    )
    return profile
