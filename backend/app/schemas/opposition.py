"""DTO du droit d'opposition (#334) — formes de `contracts/admin-oppositions.md`."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_serializer, model_validator


class OppositionIdentity(BaseModel):
    """Une fiche (`athlete_id`) **ou** un nom et un prénom, jamais les deux."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    athlete_id: int | None = None
    nom: str | None = None
    prenom: str | None = None

    @model_validator(mode="after")
    def _one_identity(self):
        by_name = bool(self.nom or self.prenom)
        if (self.athlete_id is None) == (not by_name):
            raise ValueError("Indiquez soit une fiche athlète, soit un nom et un prénom.")
        return self


class OppositionCreate(OppositionIdentity):
    requested_on: date


class OppositionPreviewRead(BaseModel):
    athletes: int
    results: int
    already_opposed: bool


class OppositionRead(BaseModel):
    id: int
    requested_on: date
    applied_at: datetime
    delay_days: int
    overdue: bool
    applied_by_name: str | None
    anonymised_count: int

    @field_serializer("applied_at")
    def _serialize_utc(self, value: datetime) -> str:
        return f"{value.isoformat()}Z"
