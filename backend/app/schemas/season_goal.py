"""DTO des objectifs de saison (#1373)."""
from typing import Literal

from pydantic import BaseModel, Field


class SeasonGoalWrite(BaseModel):
    kind: Literal["time", "count"]
    event_type: str | None = None
    #: Secondes pour un temps, nombre d'épreuves pour un nombre.
    target: int = Field(ge=1, le=2_147_483_647)


class SeasonGoalRead(BaseModel):
    id: int
    season: int
    kind: str
    event_type: str | None
    target: int
    best_time: str | None
    count: int | None
    reached: bool
