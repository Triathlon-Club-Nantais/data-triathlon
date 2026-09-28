"""Réponses des routes de statistiques (#1055) : les clés rendues jusqu'ici, à l'identique."""
from datetime import date

from pydantic import BaseModel


class RankBucket(BaseModel):
    victories: int
    podiums: int
    top10: int


class GenderRankCounters(BaseModel):
    women: RankBucket
    men: RankBucket


class RankCounters(BaseModel):
    """Victoires/podiums/top 10 des quatre modes de rang du tableau de bord."""

    scratch: RankBucket
    category: RankBucket
    all: RankBucket
    gender: GenderRankCounters


class RecentResult(BaseModel):
    id: int
    athlete_name: str
    athlete_firstname: str
    club: str
    event_name: str
    event_type: str
    event_date: str | None
    total_time: str
    scraped_at: str | None


class StatsOut(BaseModel):
    total: int
    athletes: int
    events: int
    by_type: dict[str, int]
    by_month: dict[str, int]
    recent: list[RecentResult]
    rank_counters: RankCounters


class GeoEvent(BaseModel):
    course_id: int
    event_name: str
    event_date: date | None
    event_type: str
    count: int
    tcn_count: int
    lat: float
    lon: float
