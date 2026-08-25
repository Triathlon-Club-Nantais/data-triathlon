"""Schémas Pydantic pour la synthèse club (#581)."""
from pydantic import BaseModel


class ClubRosterEntry(BaseModel):
    """Un athlète du roster club, avec ses podiums ventilés par portée."""

    athlete_id: int
    prenom: str
    nom: str
    count: int
    podiums: int
    podiums_overall: int
    podiums_gender: int
    podiums_category: int


class ClubPodiumEntry(BaseModel):
    """Une participation podium, aplatie pour l'affichage (pas d'objet imbriqué)."""

    participation_id: int
    athlete_id: int
    athlete_name: str
    event_name: str
    event_type: str
    is_relay: bool
    event_date: str | None = None
    rank: int
    scope: str
    total_time: str | None = None


class ClubPodiums(BaseModel):
    """Podiums du club, ventilés par mode de rang (miroir de `rank_counters`)."""

    scratch: list[ClubPodiumEntry]
    category: list[ClubPodiumEntry]
    gender: list[ClubPodiumEntry]
    all: list[ClubPodiumEntry]


class ClubSummary(BaseModel):
    roster: list[ClubRosterEntry]
    podiums: ClubPodiums
