"""Schémas Pydantic pour Course et la vue agrégée des épreuves."""
from datetime import date

from pydantic import BaseModel, ConfigDict


class CourseBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    event_date: date | None = None
    event_type: str = ""
    provider: str = ""
    source_url: str = ""
    is_relay: bool = False


class EventOut(BaseModel):
    """Épreuve distincte avec compteurs (vue liste / groupes)."""

    event_name: str
    event_date: str | None = None
    event_type: str = ""
    total: int
    tcn_count: int
