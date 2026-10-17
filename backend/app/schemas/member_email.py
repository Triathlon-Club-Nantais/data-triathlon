"""DTO des adresses d'adhérents (#1334)."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt


class MemberEmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    season: int
    source: Literal["import", "manual"]
    created_at: datetime


class MemberEmailsSeasonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    counting_season: int
    seasons: list[int]
    entries: list[MemberEmailOut]


class MemberEmailCreate(BaseModel):
    # `str` et non `EmailStr` : la validation passe par le service, pour un 422
    # français à la forme `{"detail": "<chaîne>"}` (même choix qu'`AllowedEmailCreate`).
    email: str
    season: StrictInt


class MemberEmailsImportReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    added: int
    removed: int
    unchanged: int
    ignored: int
