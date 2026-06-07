"""Schémas Pydantic pour Participation (sortie imbriquée et création manuelle)."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.schemas.athlete import AthleteBrief
from app.schemas.course import CourseBrief


class ParticipationOut(BaseModel):
    """Résultat d'un athlète sur une course, athlète + course imbriqués."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete: AthleteBrief
    course: CourseBrief
    club: str | None = None
    category: str | None = None
    bib_number: str | None = None
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str | None = None
    status: str = "finisher"
    splits: dict[str, str] | None = None
    created_at: datetime | None = None


class ParticipationCreate(BaseModel):
    """
    Création manuelle d'un résultat. Porte l'identité de l'athlète et de la course
    (forme plate) ; le service les normalise en Athlete + Course + Participation.
    """

    # Source / provider
    source_url: str = ""
    provider: str = "manuel"
    # Athlète
    athlete_name: str = ""
    athlete_firstname: str = ""
    gender: str = ""
    club: str = ""
    # Épreuve
    event_name: str = ""
    event_date: str | None = None
    event_type: str = ""
    is_relay: bool = False
    # Participation
    bib_number: str = ""
    category: str = ""
    rank_overall: int | None = None
    rank_category: int | None = None
    rank_gender: int | None = None
    total_time: str = ""
    # Segments (mappés vers splits)
    swim_time: str = ""
    t1_time: str = ""
    bike_time: str = ""
    t2_time: str = ""
    run_time: str = ""
    raw_data: dict = {}
