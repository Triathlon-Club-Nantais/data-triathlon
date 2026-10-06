"""DTO de la revue d'identité des athlètes (#908)."""
from datetime import date, datetime

from pydantic import BaseModel, StrictInt


class IdentityReviewAthlete(BaseModel):
    id: int
    nom: str
    prenom: str
    club: str | None
    gender: str
    categories: list[str]
    participations: int
    homonym_rank: int


class IdentityReviewEntry(BaseModel):
    participation_id: int
    athlete_id: int
    bib: str | None
    category: str | None
    total_time: str | None


class IdentityReviewConflict(BaseModel):
    course_id: int
    course_name: str
    event_date: date | None
    entries: list[IdentityReviewEntry]


class IdentityReviewClub(BaseModel):
    """Un club à vérifier sur une fiche (`multi_club`, #1209)."""

    club: str
    club_key: str
    results: int


class IdentityReviewCandidate(BaseModel):
    reason: str
    reason_label: str
    athletes: list[IdentityReviewAthlete]
    conflicts: list[IdentityReviewConflict]
    clubs: list[IdentityReviewClub] = []


class IdentityReviewList(BaseModel):
    candidates: list[IdentityReviewCandidate]


class IdentityReviewCount(BaseModel):
    total: int


class IdentityPairIgnoreCreate(BaseModel):
    athlete_id_a: StrictInt
    athlete_id_b: StrictInt


class IdentityPairIgnoreOut(BaseModel):
    athlete_id_a: int
    athlete_id_b: int
    ignored_at: datetime


class IdentityClubConfirmCreate(BaseModel):
    athlete_id: StrictInt
    club_key: str


class IdentityClubConfirmOut(BaseModel):
    athlete_id: int
    club_key: str
    confirmed_at: datetime
