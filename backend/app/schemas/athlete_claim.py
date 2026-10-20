"""DTO du rattachement d'un compte à sa fiche athlète (#1325)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.schemas.ids import DbId
from app.schemas.utc_datetime import UtcDatetime


class ClaimedAthleteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    prenom: str
    nom: str


class AthleteClaimCreate(BaseModel):
    athlete_id: DbId


class AthleteClaimRead(BaseModel):
    """La demande du compte, telle que son auteur la voit."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete: ClaimedAthleteRead
    status: Literal["pending", "rejected"]
    created_at: UtcDatetime


class ClaimantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    display_name: str
    email: str


class ReviewedAthleteRead(ClaimedAthleteRead):
    club: str | None


class LicenseeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    prenom: str
    nom: str
    season: int


class AthleteLinkRead(BaseModel):
    """Un compte rattaché, vu du club (#1633)."""

    model_config = ConfigDict(from_attributes=True)

    user: ClaimantRead
    athlete: ReviewedAthleteRead
    licensed_this_season: bool


class ResultClaimCreate(BaseModel):
    participation_id: DbId


class ResultClaimRead(BaseModel):
    """Une réclamation de résultat, vue de son auteur (#1637)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    participation_id: int
    status: Literal["pending", "rejected"]
    created_at: UtcDatetime
    course_id: int
    course_name: str
    event_date: str | None


class ClaimedResultRead(BaseModel):
    id: int
    course_id: int
    course_name: str
    event_date: str | None
    event_type: str
    bib_number: str | None
    total_time: str | None
    club: str | None
    category: str | None


class ResultClaimReviewRead(BaseModel):
    """Une réclamation de la file, avec ses indices (#1637)."""

    id: int
    created_at: UtcDatetime
    user: ClaimantRead
    participation: ClaimedResultRead
    current_athlete: ReviewedAthleteRead
    current_athlete_results: int
    claimant_athlete: ReviewedAthleteRead | None
    licensee: LicenseeRead | None


class AthleteClaimReviewRead(BaseModel):
    """Une demande de la file, avec ses indices (contracts/admin-athlete-claims.md)."""

    id: int
    created_at: UtcDatetime
    user: ClaimantRead
    athlete: ReviewedAthleteRead
    licensee: LicenseeRead | None
    email_on_member_list: bool
    linked_accounts: int
