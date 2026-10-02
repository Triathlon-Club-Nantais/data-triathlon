"""Schémas des classements Challenge (#1008). Tous additifs au contrat `/api/v1`."""
from datetime import date

from pydantic import BaseModel


class ChallengeCourseOut(BaseModel):
    id: int
    name: str


class AthleteChallengeOut(BaseModel):
    """Ligne Challenge vue depuis la fiche athlète."""

    id: int
    name: str
    event_date: date
    rank_overall: int | None
    #: Nombre de lignes classées du Challenge, pour lire « 1er / 52 ».
    ranked_count: int
    total_time: str | None
    courses: list[ChallengeCourseOut]


class CourseChallengeOut(BaseModel):
    """Challenge auquel compte une épreuve."""

    id: int
    name: str
    ranked_count: int


class ChallengeResultOut(BaseModel):
    athlete_id: int
    nom: str
    prenom: str
    rank_overall: int | None
    total_time: str | None
    status: str


class ChallengeDetail(BaseModel):
    """`GET /challenges/{id}` : le classement, trié par rang, les non classés en fin."""

    id: int
    name: str
    event_date: date
    courses: list[ChallengeCourseOut]
    results: list[ChallengeResultOut]
