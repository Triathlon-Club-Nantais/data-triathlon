"""Accès données pour PersonalProfile et ProfileLogEntry — seule couche qui
touche la Session (#867).

La transaction reste portée par le service appelant (`services/profile_service.py`),
comme partout ailleurs : on `flush()` pour peupler l'id, on ne `commit()` jamais
ici. Patron `app/repositories/group_repository.py`.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.personal_profile import PersonalProfile
from app.models.profile_log_entry import ProfileLogEntry


def get(db: Session, profile_id: int) -> PersonalProfile | None:
    return db.get(PersonalProfile, profile_id)


def list_all(db: Session) -> list[PersonalProfile]:
    """Les profils, triés par nom puis prénom (US1 de spec.md)."""
    return list(
        db.scalars(
            select(PersonalProfile).order_by(
                PersonalProfile.last_name, PersonalProfile.first_name
            )
        )
    )


def create(
    db: Session,
    *,
    organisation_id: int,
    first_name: str,
    last_name: str,
    birth_date: date | None = None,
    emergency_contact: str = "",
    notes: str = "",
    created_by_user_id: int | None = None,
) -> PersonalProfile:
    profile = PersonalProfile(
        organisation_id=organisation_id,
        first_name=first_name,
        last_name=last_name,
        birth_date=birth_date,
        emergency_contact=emergency_contact,
        notes=notes,
        created_by_user_id=created_by_user_id,
    )
    db.add(profile)
    db.flush()
    return profile


def update(db: Session, profile: PersonalProfile, **champs) -> PersonalProfile:
    """Modifie uniquement les champs fournis — `None` n'efface rien ici.

    C'est au service de décider ce qui est « fourni » (patron `PATCH` partiel
    de `services/auth/groups.update_group`) ; ce repository applique tel quel
    ce qu'on lui passe.
    """
    for champ, valeur in champs.items():
        setattr(profile, champ, valeur)
    db.flush()
    return profile


def list_log_entries(db: Session, profile_id: int) -> list[ProfileLogEntry]:
    """Les entrées d'un profil, la plus récente en premier (US2 de spec.md)."""
    return list(
        db.scalars(
            select(ProfileLogEntry)
            .where(ProfileLogEntry.profile_id == profile_id)
            .order_by(ProfileLogEntry.entry_date.desc(), ProfileLogEntry.created_at.desc())
        )
    )


def add_log_entry(
    db: Session,
    *,
    profile_id: int,
    text: str,
    entry_date: date | None = None,
    created_by_user_id: int | None = None,
) -> ProfileLogEntry:
    entry = ProfileLogEntry(
        profile_id=profile_id,
        text=text,
        entry_date=entry_date or date.today(),
        created_by_user_id=created_by_user_id,
    )
    db.add(entry)
    db.flush()
    return entry
