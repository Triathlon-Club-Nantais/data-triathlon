"""DTO du formulaire public de déclaration de bénévolat (#778) et de son
workflow de validation admin (#779).

Noms distincts de `VolunteerActionCreate`/`VolunteerActionOut` de
`schemas/admin.py` (chemin admin existant, #709, inchangé) — collision de
noms relevée par `/speckit-analyze` (finding C1)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VolunteerActionSelfCreate(BaseModel):
    """Corps de `POST /api/v1/volunteer-actions` — self-service.

    Pas de champ `season` ni `status` : la saison est dérivée côté serveur
    (`current_season()`, research.md D5) et le statut est toujours posé à
    « en attente » par le service (FR-009)."""

    model_config = ConfigDict(str_strip_whitespace=True)

    athlete_id: int
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)


class VolunteerActionSelfOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    season: int
    title: str
    description: str
    status: str
    declared_by_user_id: int | None
    created_at: datetime


class AdminVolunteerActionOut(BaseModel):
    """File d'attente admin (#779) — `title`/`description` optionnels : le
    chemin de création admin existant (#709) ne les renseigne jamais
    (research.md D5 de #779)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    season: int
    title: str | None
    description: str | None
    status: str
    declared_by_user_id: int | None
    created_at: datetime
