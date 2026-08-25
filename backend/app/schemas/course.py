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


class CourseSourceSwitch(BaseModel):
    """Le corps de la bascule d'une source active (#285). Un seul champ, obligatoire.

    `is_active` et non un corps vide, parce que l'écran (#291) est une liste de
    sources dont on coche celle qui fait foi : la requête dit l'état voulu.
    **`false` n'est pas un geste** — le refus vit dans la route, pas dans une
    contrainte Pydantic, dont le 422 rendrait un `detail` en liste d'objets et un
    message anglais (même parti pris qu'`AllowedEmailCreate`, cf. FR-010).
    """

    is_active: bool


class CourseBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    event_date: date | None = None
    event_type: str = ""
    provider: str = ""
    source_url: str = ""
    is_relay: bool = False
    format_label: str | None = None
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
    #: Miroir des deux champs de `CourseBrief` (#486). Sans eux, la liste des
    #: épreuves ne peut pas marquer ce qu'elle liste sans un second appel, alors
    #: que sa requête agrège déjà par `Course.id`. `None` = épreuve jamais
    #: évaluée, état normal des imports antérieurs au calcul de fiabilité.
    is_reliable: bool | None = None
    quality_issues: dict[str, int] | None = None


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
    #: Ventilation de `non_finishers` par statut (#331) — un DNS n'a jamais
    #: pris le départ, un DSQ a couru et a été disqualifié, ce n'est ni l'un
    #: ni l'autre un abandon (DNF). `non_finishers` reste leur somme.
    dnf: int
    dns: int
    dsq: int
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
    #: Médiane des écarts `(total − Σ inters) / total` des lignes évaluables (#486).
    #: C'est la **référence** à laquelle se juge l'écart d'une ligne : un écart
    #: partagé par toute l'épreuve est un segment que le chronométreur ne publie
    #: pas, pas une ligne fausse. `None` quand aucune ligne n'est évaluable.
    #:
    #: Une **mesure**, jamais un verdict : les seuils d'affichage vivent côté
    #: écran, ce qui permet de les régler après re-sondage sans toucher au
    #: contrat. Point de vérité des seuils :
    #: `docs/superpowers/specs/2026-08-25-ecart-inters-total-sondage.md`.
    split_gap_median: float | None = None
    #: Nombre de lignes **évaluables** de l'épreuve — celles sur lesquelles la
    #: médiane est calculée. Sans lui, l'écran ne peut pas appliquer la garde
    #: d'effectif du sondage : la médiane d'une population de neuf n'est pas une
    #: référence, et la course 65 (neuf enfants, totaux de cinq minutes) faisait
    #: signaler deux lignes pour vingt secondes.
    split_gap_rows: int = 0
