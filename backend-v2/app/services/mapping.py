"""
Conversion d'un `ScrapedResult` (sortie des scrapers, modèle plat) vers les
entités normalisées Athlete / Course / Participation.

Les segments de temps (natation, T1, vélo, T2, course…) sont regroupés dans un
dict `splits` adapté au sport, plutôt que des colonnes figées.
"""
from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.course import Course
from app.repositories import athlete_repository, course_repository
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult

# Les scrapers rangent toujours les segments dans 5 slots positionnels triathlon
# (swim/t1/bike/t2/run). Selon le sport, on ré-étiquette ces slots avec des clés
# parlantes et on omet les slots non pertinents. Gabarit = {champ ScrapedResult: clé splits}.
# Le triathlon est le défaut (clés = nom du slot sans le suffixe `_time`).
_DEFAULT_SPLIT_KEYS = {
    "swim_time": "swim", "t1_time": "t1", "bike_time": "bike",
    "t2_time": "t2", "run_time": "run",
}
_SPLIT_KEYS_BY_SPORT: dict[str, dict[str, str]] = {
    # Duathlon : course à pied 1 → slot swim, course à pied 2 → slot run.
    "duathlon": {
        "swim_time": "course1", "t1_time": "t1", "bike_time": "bike",
        "t2_time": "t2", "run_time": "course2",
    },
    "aquathlon": {"swim_time": "swim", "t1_time": "t1", "run_time": "run"},
    "aquarun": {"swim_time": "swim", "t1_time": "t1", "run_time": "run"},
    "bike-run": {"bike_time": "bike", "run_time": "run"},
    "swimrun": {"swim_time": "swim", "run_time": "run"},
}


def _sport_base(event_type: str) -> str:
    """Préfixe de sport sans le suffixe de taille : ``duathlon-m`` → ``duathlon``.

    ``bike-run`` n'a pas de suffixe de taille : le tiret fait partie du nom.
    """
    et = (event_type or "").lower()
    if et.startswith("bike-run"):
        return "bike-run"
    return et.split("-", 1)[0]


def build_splits(scraped: ScrapedResult) -> dict[str, str]:
    """Construit le dict des temps intermédiaires non vides, clés adaptées au sport."""
    template = _SPLIT_KEYS_BY_SPORT.get(_sport_base(scraped.event_type), _DEFAULT_SPLIT_KEYS)
    return {
        key: getattr(scraped, field)
        for field, key in template.items()
        if getattr(scraped, field)
    }


def derive_status(scraped: ScrapedResult) -> str:
    """Statut sportif. Respecte le statut explicite du scraper s'il existe,
    sinon retombe sur l'heuristique (finisher si temps total, sinon DNF)."""
    if scraped.status:
        return scraped.status
    return STATUS_FINISHER if scraped.total_time else STATUS_DNF


def get_or_create_course(db: Session, scraped: ScrapedResult, event_url: str) -> Course:
    """Course identifiée par (nom, date, type) ; `source_url` = URL d'import (clé de cache)."""
    return course_repository.get_or_create(
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
    return athlete_repository.get_or_create(
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
