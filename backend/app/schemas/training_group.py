"""DTO des groupes d'entraînement (#1291), contracts/api.md section Groupes."""
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.profile import ProfileRead


class TrainingGroupRead(BaseModel):
    id: int
    name: str
    member_count: int


class TrainingGroupDetailRead(BaseModel):
    id: int
    name: str
    members: list[ProfileRead]


class TrainingGroupWrite(BaseModel):
    """Le nom est nettoyé et validé par le service, pour un refus en français."""

    model_config = ConfigDict(extra="forbid")

    name: str


class TrainingGroupMemberAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: int = Field(gt=0)
