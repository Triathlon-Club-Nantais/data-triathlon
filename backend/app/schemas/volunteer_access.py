"""DTO de la gestion admin du mot de passe partagé bénévoles
(`specs/20260815-173645-admin-mdp-benevoles/contracts/api.md`)."""
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.site_access import MAX_PASSWORD_LENGTH


class VolunteerAccessConfigOut(BaseModel):
    """État courant — **jamais** le mot de passe ni son empreinte (FR-004)."""

    configured: bool
    updated_at: datetime | None = None
    updated_by: str | None = None


class VolunteerAccessReplaceIn(BaseModel):
    """Corps de `PUT /admin/benevoles/access` (Story 1)."""

    # Même borne que `VolunteerLogin`, sinon la connexion refuserait en 422 le
    # mot de passe posé ici.
    password: str = Field(min_length=8, max_length=MAX_PASSWORD_LENGTH)


class VolunteerAccessGeneratedOut(BaseModel):
    """Réponse de `POST /admin/benevoles/access/generate` (Story 2) — la
    **seule** route qui renvoie jamais un mot de passe en clair (FR-003)."""

    password: str
    updated_at: datetime
    updated_by: str
