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
from app.scrapers.classify import extract_distance_km

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
    # Mono-sports : un seul segment pertinent.
    "course-a-pied": {"run_time": "run"},
    "trail": {"run_time": "run"},
    "cyclisme": {"bike_time": "bike"},
}

# Bases de sport dont le nom contient un tiret (le tiret ne sépare pas la taille).
_MULTI_WORD_BASES = ("bike-run", "course-a-pied")


def _sport_base(event_type: str) -> str:
    """Préfixe de sport sans suffixe de taille : ``duathlon-m`` → ``duathlon``.

    Les bases multi-mots (``bike-run``, ``course-a-pied``) contiennent un tiret
    qui fait partie du nom, pas un séparateur de taille.
    """
    et = (event_type or "").lower()
    for base in _MULTI_WORD_BASES:
        if et.startswith(base):
            return base
    return et.split("-", 1)[0]


def build_splits(scraped: ScrapedResult) -> dict[str, str]:
    """Construit le dict des temps intermédiaires non vides, clés adaptées au sport.

    Si le scraper fournit `segments` (chemin générique, déplafonné, étiquettes
    libres), il prime sur les 5 slots positionnels. Sinon, on ré-étiquette les
    slots selon le sport.

    Les libellés de `segments` ne sont pas garantis uniques (deux colonnes
    peuvent se réduire au même libellé après i18n) : on désambiguïse par un
    suffixe ` (N)` plutôt que d'écraser silencieusement un temps.
    """
    if scraped.segments:
        splits: dict[str, str] = {}
        for label, time in scraped.segments:
            if not time:
                continue
            key, n = label, 2
            while key in splits:
                key = f"{label} ({n})"
                n += 1
            splits[key] = time
        return splits
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
    distance_km = scraped.distance_km
    if distance_km is None:
        distance_km = extract_distance_km(scraped.event_name)
    return course_repository.get_or_create(
        db,
        name=scraped.event_name,
        event_date=scraped.event_date,
        event_type=scraped.event_type,
        source_url=event_url or scraped.source_url,
        provider=scraped.provider,
        is_relay=scraped.is_relay,
        distance_km=distance_km,
    )


def resolve_athlete(db: Session, scraped: ScrapedResult) -> tuple[Athlete, bool]:
    """Athlète dédoublonné + drapeau « créé » (True = renommage, False = fusion)."""
    return athlete_repository.resolve(
        db,
        nom=scraped.athlete_name,
        prenom=scraped.athlete_firstname,
        gender=scraped.gender,
        club=scraped.club or None,
    )


def get_or_create_athlete(db: Session, scraped: ScrapedResult) -> Athlete:
    """Athlète dédoublonné par nom + prénom (+ date de naissance si connue)."""
    athlete, _ = resolve_athlete(db, scraped)
    return athlete


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
        "is_relay": scraped.is_relay,
        "rank_overall": scraped.rank_overall,
        "rank_category": scraped.rank_category,
        "rank_gender": scraped.rank_gender,
        "total_time": scraped.total_time or None,
        "status": derive_status(scraped),
        "splits": build_splits(scraped) or None,
        "raw_data": scraped.raw_data or None,
    }
