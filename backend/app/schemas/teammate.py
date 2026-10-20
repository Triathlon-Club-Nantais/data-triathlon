"""Coéquipiers de course de l'athlète connecté (#1701)."""
from pydantic import BaseModel


class Teammate(BaseModel):
    athlete_id: int
    prenom: str
    nom: str
    courses_communes: int
