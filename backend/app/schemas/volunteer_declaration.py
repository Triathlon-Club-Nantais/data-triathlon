"""DTO de la déclaration de bénévolat (#751) — formes de
`contracts/volunteer-declaration-api.md`."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VolunteerDeclarationCreate(BaseModel):
    """Corps de `POST /api/v1/volunteer-declarations` — self-service.

    **Aucun champ bénéficiaire** : c'est ce qui rend structurel le refus d'un
    membre standard de déclarer au nom d'un tiers (FR-003) — le bénéficiaire
    est toujours déduit de `current_user` côté serveur.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)


class VolunteerDeclarationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    status: str
    beneficiary_user_id: int
    author_user_id: int
    created_at: datetime


class AdminVolunteerDeclarationCreate(BaseModel):
    """Corps de `POST /admin/volunteer-declarations` — réservé à
    `benevolat:manage`. Seule forme portant un bénéficiaire explicite."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    beneficiary_user_id: int


class AdminVolunteerDeclarationOut(VolunteerDeclarationOut):
    """Étend `VolunteerDeclarationOut` avec l'identité du bénéficiaire —
    patron `AdminAthleteRead` vs `AthleteRead`."""

    beneficiary_display_name: str
    beneficiary_email: str
