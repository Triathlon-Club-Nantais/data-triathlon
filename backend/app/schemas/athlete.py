"""Schémas Pydantic pour Athlete."""
from pydantic import BaseModel, ConfigDict


class AthleteBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nom: str
    prenom: str = ""
    gender: str = ""
    club: str | None = None
