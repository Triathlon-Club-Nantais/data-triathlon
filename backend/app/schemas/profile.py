"""DTO des profils individuels (#867) — formes de `contracts/admin-profiles.md`.

Patron `app/schemas/admin.py` (`GroupRead`/`GroupCreate`/`GroupUpdate`).
"""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ProfileLogEntryRead(BaseModel):
    """Une entrée du journal de bord, telle que rendue dans l'historique."""

    id: int
    entry_date: date
    text: str
    created_by_name: str | None
    created_at: datetime


class ProfileLogEntryCreate(BaseModel):
    """Corps de `POST /admin/profiles/{id}/log-entries`.

    `entry_date` absente vaut la date du jour (posé côté service) — une
    saisie a posteriori reste possible en la fournissant explicitement.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    text: str = Field(min_length=1)
    entry_date: date | None = None


class ProfileRead(BaseModel):
    """Un profil tel qu'il apparaît dans la liste — sans journal ni contact
    d'urgence, pas nécessaire pour un aperçu (patron `GroupRead`)."""

    id: int
    organisation_id: int
    first_name: str
    last_name: str
    birth_date: date | None
    created_at: datetime


class ProfileDetailRead(ProfileRead):
    """Un profil et son journal — la ressource qui justifie l'objet entier."""

    emergency_contact: str
    notes: str
    log_entries: list[ProfileLogEntryRead]


class ProfileCreate(BaseModel):
    """Création d'un profil. Nom et prénom sont les deux seuls champs requis
    (FR-003 de spec.md)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    birth_date: date | None = None
    emergency_contact: str = ""
    notes: str = ""


class ProfileUpdate(BaseModel):
    """Modification d'un profil. Tous les champs sont facultatifs et
    indépendants — `None` (absent) = non modifié (patron `GroupUpdate`)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str | None = Field(default=None, min_length=1)
    last_name: str | None = Field(default=None, min_length=1)
    birth_date: date | None = None
    emergency_contact: str | None = None
    notes: str | None = None
