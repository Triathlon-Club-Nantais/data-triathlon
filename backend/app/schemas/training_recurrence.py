"""DTO des séances récurrentes (#1291), contracts/api.md section Récurrences."""
from datetime import date
from datetime import time as time_

from pydantic import BaseModel, ConfigDict, Field


class TrainingRecurrenceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    #: 0 = lundi, 6 = dimanche.
    weekday: int = Field(ge=0, le=6)
    start_time: time_ | None = None
    location: str | None = None
    session_type: str | None = None
    starts_on: date
    ends_on: date
    group_ids: list[int] = []


class TrainingRecurrenceUpdate(BaseModel):
    """Tous les champs optionnels : absent = inchangé."""

    model_config = ConfigDict(extra="forbid")

    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: time_ | None = None
    location: str | None = None
    session_type: str | None = None
    starts_on: date | None = None
    ends_on: date | None = None
    group_ids: list[int] | None = None


class TrainingRecurrenceRead(BaseModel):
    id: int
    weekday: int
    start_time: time_ | None
    location: str | None
    session_type: str | None
    starts_on: date
    ends_on: date
    group_ids: list[int]
    upcoming_session_count: int


class TrainingRecurrenceCreated(TrainingRecurrenceRead):
    created_session_count: int


class TrainingRecurrencePreview(BaseModel):
    occurrence_count: int
    dates: list[date]


class TrainingRecurrenceDeleted(BaseModel):
    deleted_session_count: int
    kept_session_count: int
