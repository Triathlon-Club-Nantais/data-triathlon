"""
Conversion d'un `ScrapedResult` (sortie des scrapers, modèle plat) vers les
entités normalisées Athlete / Course / Participation.

Les segments de temps (natation, T1, vélo, T2, course…) sont regroupés dans un
dict `splits` adapté au sport, plutôt que des colonnes figées.
"""
from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import athlete_repo, course_repo
from app.scrapers.base import ScrapedResult

# Segments standards exposés par ScrapedResult → clés du dict splits.
_SEGMENT_FIELDS = ("swim_time", "t1_time", "bike_time", "t2_time", "run_time")


def build_splits(scraped: ScrapedResult) -> dict[str, str]:
    """Construit le dict des temps intermédiaires non vides."""
    return {
        field.removesuffix("_time"): getattr(scraped, field)
        for field in _SEGMENT_FIELDS
        if getattr(scraped, field)
    }


def derive_status(scraped: ScrapedResult) -> str:
    """Statut sportif : finisher si un temps total existe, sinon DNF."""
    return "finisher" if scraped.total_time else "DNF"


def get_or_create_course(db: Session, scraped: ScrapedResult, event_url: str) -> Course:
    """Course identifiée par (nom, date, type) ; `source_url` = URL d'import (clé de cache)."""
    return course_repo.get_or_create(
        db,
        name=scraped.event_name,
        event_date=scraped.event_date,
        event_type=scraped.event_type,
        source_url=event_url or scraped.source_url,
        provider=scraped.provider,
        is_relay=scraped.is_relay,
    )


def get_or_create_athlete(db: Session, scraped: ScrapedResult) -> Athlete:
    """Athlète dédoublonné par nom + prénom (+ date de naissance si connue)."""
    return athlete_repo.get_or_create(
        db,
        nom=scraped.athlete_name,
        prenom=scraped.athlete_firstname,
        gender=scraped.gender,
        club=scraped.club or None,
    )


def participation_fields(
    scraped: ScrapedResult, *, athlete_id: int, course_id: int
) -> dict:
    """Champs d'une Participation à partir d'un ScrapedResult."""
    return {
        "athlete_id": athlete_id,
        "course_id": course_id,
        "club": scraped.club or None,
        "category": scraped.category or None,
        "bib_number": scraped.bib_number or None,
        "rank_overall": scraped.rank_overall,
        "rank_category": scraped.rank_category,
        "rank_gender": scraped.rank_gender,
        "total_time": scraped.total_time or None,
        "status": derive_status(scraped),
        "splits": build_splits(scraped) or None,
        "raw_data": scraped.raw_data or None,
    }
