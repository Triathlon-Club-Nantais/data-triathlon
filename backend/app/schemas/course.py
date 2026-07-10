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
    distance_km: float | None = None
    # Indice de fiabilité calculé à l'import. `None` = course jamais évaluée.
    is_reliable: bool | None = None
    quality_issues: dict[str, int] | None = None


class EventOut(BaseModel):
    """Épreuve distincte avec compteurs (vue liste / groupes)."""

    id: int
    event_name: str
    event_date: str | None = None
    event_type: str = ""
    is_relay: bool = False
    distance_km: float | None = None
    total: int
    tcn_count: int


class EventPage(BaseModel):
    """Page d'épreuves pour le scroll infini + compteurs globaux du filtre."""

    items: list[EventOut]
    total_events: int
    total_participations: int
