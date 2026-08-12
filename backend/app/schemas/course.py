"""Schémas Pydantic pour Course et la vue agrégée des épreuves."""
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CourseSourceOut(BaseModel):
    """Une source de chronométrage d'une épreuve, telle que la voit **le public** (#284).

    Ici et non dans un `schemas/course_source.py` à part : la ressource est
    servie par le router `courses` et n'a pas d'existence hors d'une épreuve —
    c'est aussi ce que demande l'issue.

    **Cinq champs, et l'absence du sixième est le contrat.**
    `created_by_user_id` — comme la relation `created_by` — reste interne : une
    route ouverte n'a aucune raison de nommer qui a soumis une URL. Rien ne le
    remonterait par accident (Pydantic ne sérialise que les champs déclarés),
    mais l'inverse serait vrai d'un `model_config` mal recopié, d'où le test
    explicite de `tests/test_api/test_course_sources_api.py`.

    `last_scraped_at` est celui de **cette** source, pas de l'épreuve : une
    passive n'est jamais scrapée, donc `null` y est la valeur normale.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    provider: str = ""
    is_active: bool = False
    last_scraped_at: datetime | None = None


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


class CourseCount(BaseModel):
    """Le total du catalogue aux filtres courants — le « sur 7 » d'une pagination."""

    total: int


class EventPage(BaseModel):
    """Page d'épreuves pour le scroll infini + compteurs globaux du filtre."""

    items: list[EventOut]
    total_events: int
    total_participations: int


class CategoryCount(BaseModel):
    name: str
    count: int


class ClubCount(BaseModel):
    name: str
    count: int
    is_tcn: bool


class Histogram(BaseModel):
    """Distribution des temps par tranches.

    `start_sec` est le bord gauche de la première tranche : il publie l'ancrage
    temporel pour que l'axe des abscisses s'aligne sur des heures rondes (#129).
    """

    bars: list[int]
    start_sec: int
    bucket_sec: int


class CourseSummary(BaseModel):
    """Synthèse d'une épreuve **entière** (#163).

    Aucun de ses champs ne dépend de la recherche ni de la portée club en cours :
    chercher un nom ne doit pas faire tomber l'histogramme à une barre. C'est
    pour cela que la route qui la sert n'accepte aucun paramètre.
    """

    total: int
    finishers: int
    non_finishers: int
    unknown: int
    tcn_count: int
    male: int
    female: int
    categories: list[CategoryCount]
    #: Somme sur **toutes** les catégories, dénominateur des pourcentages.
    categories_total: int
    clubs: list[ClubCount]
    histogram: Histogram | None = None
    split_keys: list[str]
