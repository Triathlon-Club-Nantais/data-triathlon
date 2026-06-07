"""Schémas Pydantic pour le scraping (requête + prévisualisation)."""
from pydantic import BaseModel

from app.scrapers.base import ScrapedResult


class ScrapeRequest(BaseModel):
    url: str
    bib: str | None = None


class ScrapedPreview(BaseModel):
    """Prévisualisation d'un athlète scrapé (non persisté), éditable côté frontend."""

    provider: str
    source_url: str
    athlete_name: str
    athlete_firstname: str
    club: str
    category: str
    gender: str
    bib_number: str
    event_name: str
    event_date: str | None
    event_type: str
    rank_overall: int | None
    rank_category: int | None
    rank_gender: int | None
    total_time: str
    swim_time: str
    t1_time: str
    bike_time: str
    t2_time: str
    run_time: str
    is_relay: bool
    raw_data: dict

    @classmethod
    def from_scraped(cls, r: ScrapedResult) -> "ScrapedPreview":
        return cls(
            provider=r.provider,
            source_url=r.source_url,
            athlete_name=r.athlete_name,
            athlete_firstname=r.athlete_firstname,
            club=r.club,
            category=r.category,
            gender=r.gender,
            bib_number=r.bib_number,
            event_name=r.event_name,
            event_date=r.event_date.isoformat() if r.event_date else None,
            event_type=r.event_type,
            rank_overall=r.rank_overall,
            rank_category=r.rank_category,
            rank_gender=r.rank_gender,
            total_time=r.total_time,
            swim_time=r.swim_time,
            t1_time=r.t1_time,
            bike_time=r.bike_time,
            t2_time=r.t2_time,
            run_time=r.run_time,
            is_relay=r.is_relay,
            raw_data=r.raw_data,
        )


class ImportResult(BaseModel):
    imported: int
    skipped: int
    cached: bool = False
