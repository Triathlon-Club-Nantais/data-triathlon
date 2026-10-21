"""DTO des objectifs de saison (#1373, #1694)."""
from datetime import date
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from app.schemas.ids import DbId

if TYPE_CHECKING:
    from app.services.season_goals import GoalProgress


class SeasonGoalWrite(BaseModel):
    kind: Literal["time", "count", "race"]
    event_type: str | None = None
    #: Secondes pour un temps, nombre d'épreuves pour un nombre, temps visé facultatif pour une épreuve cible.
    target: int | None = Field(None, ge=1, le=2_147_483_647)
    course_id: DbId | None = None
    race_name: str | None = Field(None, max_length=200)
    race_date: date | None = None
    major: bool = False
    public: bool = False


class SeasonGoalRead(BaseModel):
    id: int
    season: int
    kind: str
    event_type: str | None
    target: int | None
    best_time: str | None
    count: int | None
    reached: bool
    course_id: int | None
    race_name: str | None
    race_date: str | None
    major: bool
    public: bool
    outcome: Literal["upcoming", "awaiting_results", "reached", "missed"]

    @classmethod
    def of(cls, progress: "GoalProgress") -> "SeasonGoalRead":
        goal = progress.goal
        return cls(
            id=goal.id, season=goal.season, kind=goal.kind, event_type=goal.event_type, target=goal.target,
            best_time=progress.best_time, count=progress.count, reached=progress.reached,
            course_id=goal.course_id, race_name=goal.race_name,
            race_date=goal.race_date.isoformat() if goal.race_date else None, major=goal.major,
            public=goal.public, outcome=progress.outcome,
        )
