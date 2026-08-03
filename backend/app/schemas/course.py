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
