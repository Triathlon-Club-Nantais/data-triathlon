"""
Conversion d'un `ScrapedResult` (sortie des scrapers, modèle plat) vers les
entités normalisées Athlete / Course / Participation.

Les segments de temps (natation, T1, vélo, T2, course…) sont regroupés dans un
dict `splits` adapté au sport, plutôt que des colonnes figées.
"""
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.repositories import athlete_repository, course_repository, course_source_repository
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
from app.scrapers.classify import extract_distance_km
from app.services import course_reconciliation

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
    # Bike & Run et swimrun n'ont ni natation ni vélo à l'endroit où les slots
    # positionnels les attendent. Le slot sans discipline lisible garde une clé
    # **positionnelle** : lui donner un nom de sport mentirait, et l'omettre du
    # gabarit jetait silencieusement le temps qui s'y trouve (runnerbreizh publie
    # ses 3 colonnes de segment quelle que soit la discipline).
    "bike-run": {"swim_time": "segment1", "bike_time": "bike", "run_time": "run"},
    "swimrun": {"swim_time": "swim", "bike_time": "segment2", "run_time": "run"},
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


@dataclass(frozen=True)
class CourseResolution:
    """L'épreuve appariée, **et** la source passive que l'URL soumise y est devenue.

    Deux valeurs et non une parce que l'appelant n'a aucun moyen de reconstituer
    la seconde : une fois la source rattachée, une épreuve à deux sources est
    indistinguable de celle qu'on vient d'enrichir. `passive_source` est `None`
    dès que l'URL soumise **est** l'active — le cas nominal, y compris tout
    re-scrape.
    """
    course: Course
    passive_source: CourseSource | None


def get_or_create_course(db: Session, scraped: ScrapedResult, event_url: str) -> CourseResolution:
    """Course identifiée par (nom, date, type), et l'URL d'import rattachée en source.

    Priorité `scraped.source_url` puis `event_url` : un scraper qui a besoin
    d'une clé plus fine que l'URL soumise le dit en la posant lui-même sur
    chaque `ScrapedResult`. C'est le cas du fan-out Klikego (#156) — une URL
    d'événement scrape N heats et chacun garde sa propre URL `…?heat=X`,
    donc sa propre entrée de cache TTL. Les autres providers publient
    `scraped.source_url = url` (l'URL passée au scraper), le comportement
    est donc inchangé pour eux. `event_url` reste la voie de secours quand
    la source ne fournit pas d'URL (chemin manuel `save_one`).

    **Le rattachement est inconditionnel** (#283) : `get_or_create` ne pose la
    source que sur l'épreuve qu'il *crée*, celle qu'il apparie garde les siennes
    — c'est là que la seconde publication se perdait. `attach` étant idempotent,
    on l'appelle sans regarder lequel des deux cas on vient de traverser.

    **L'appariement tente d'abord la règle R** (#289) : Klikego et Breizh
    Chrono partagent un identifiant de plateforme dans leur `source_url`, que
    `course_reconciliation.find_reconcilable_course` compare à égalité stricte
    avec ceux déjà en base. Elle passe **avant** l'identité stricte, jamais en
    repli : les deux s'accordent déjà sur les cas où l'identité collide (même
    back-office, même nom au caractère près), donc l'ordre ne change rien pour
    eux ; c'est l'inter-façade Breizh Chrono (`live.` ↔ `resultats.`, qui
    diverge sur le nom et la date) que seule la règle R rapproche.
    """
    distance_km = scraped.distance_km
    if distance_km is None:
        distance_km = extract_distance_km(scraped.event_name)
    url = scraped.source_url or event_url
    reconciled = (
        course_reconciliation.find_reconcilable_course(
            db, provider=scraped.provider, source_url=url
        )
        if url
        else None
    )
    course = reconciled or course_repository.get_or_create(
        db,
        name=scraped.event_name,
        event_date=scraped.event_date,
        event_type=scraped.event_type,
        source_url=url,
        provider=scraped.provider,
        is_relay=scraped.is_relay,
        distance_km=distance_km,
    )
    if not url:
        # Saisie manuelle : pas d'URL, donc rien à rattacher — `CourseSource.url`
        # est `NOT NULL`, une source vide ne désignerait rien (#279).
        return CourseResolution(course=course, passive_source=None)
    source = course_source_repository.attach(
        db, course=course, url=url, provider=scraped.provider
    )
    return CourseResolution(
        course=course, passive_source=None if source.is_active else source
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
