"""DTO des licenciés du club (#1202)."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt


class ClubMemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    season: int
    licence_id: str | None
    nom: str
    prenom: str
    gender: str
    athlete_id: int | None
    link_status: Literal["auto", "manual", "unlinked", "ambiguous"]
    source: Literal["fftri", "file"]


class ClubMembersSeasonOut(BaseModel):
    season: int
    seasons: list[int]
    total: int
    linked: int
    unlinked: int
    ambiguous: int
    members: list[ClubMemberOut]


class MembersSyncReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    season: int
    total: int
    linked: int
    unlinked: int
    ambiguous: int


class ClubMemberLinkIn(BaseModel):
    athlete_id: StrictInt
