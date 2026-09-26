"""
Conversion d'un `ScrapedResult` (sortie des scrapers, modèle plat) vers les
entités normalisées Athlete / Course / Participation.

Les segments de temps (natation, T1, vélo, T2, course…) sont regroupés dans un
dict `splits` adapté au sport, plutôt que des colonnes figées.
"""
import logging
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.athlete import Athlete
from app.models.course import Course
from app.models.course_source import CourseSource
from app.repositories import athlete_repository, course_repository, course_source_repository
from app.scrapers.base import STATUS_DNF, STATUS_FINISHER, ScrapedResult
from app.scrapers.classify import extract_distance_km
from app.services import course_reconciliation

logger = logging.getLogger(__name__)

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
    # Swim Bike (#270) : pas de course à pied à l'endroit où le slot positionnel
    # l'attend — l'omettre du gabarit jetterait silencieusement un temps saisi
    # par erreur, mais le champ n'est simplement pas proposé côté saisie manuelle.
    "swim-bike": {"swim_time": "swim", "t1_time": "t1", "bike_time": "bike"},
    # Raid Multisport (#270) : aucun découpage prévisible, cf. data-model.md §6.
    "raid-multisport": {},
    # Cross Triathlon (#270) retombe sur le gabarit par défaut (natation/T1/vélo/
    # T2/course) : aucune entrée nécessaire ici.
}

# Bases de sport dont le nom contient un tiret (le tiret ne sépare pas la taille).
_MULTI_WORD_BASES = ("bike-run", "course-a-pied", "swim-bike", "cross-triathlon", "raid-multisport")


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
    else:
        template = _SPLIT_KEYS_BY_SPORT.get(_sport_base(scraped.event_type), _DEFAULT_SPLIT_KEYS)
        splits = {
            key: getattr(scraped, field)
            for field, key in template.items()
            if getattr(scraped, field)
        }
    return _plausible_splits(splits, scraped)


def _plausible_splits(splits: dict[str, str], scraped: ScrapedResult) -> dict[str, str]:
    """Écarte les segments qui ne sont pas un temps réel du parcours (#971).

    `00:00:00` est un point de passage non franchi (Klikego, Breizh Chrono), donc
    une absence, écartée sans bruit. Une durée négative ou illisible (« FRA »,
    `00:-43:-18`) et un segment plus long que le total sont journalisés. Quand
    **tous** les segments (au moins deux) valent le total, la source a recopié
    l'arrivée dans chaque inter (ProLiveSport) : aucun n'est gardé. Un segment
    unique égal au total reste légitime (mono-sport).
    """
    total = parse_duration(scraped.total_time)
    kept: dict[str, str] = {}
    for key, value in splits.items():
        seconds = parse_duration(value)
        if seconds == 0:
            continue
        if seconds is None or (total is not None and seconds > total):
            logger.info(
                "Segment écarté (%s) : %s=%r, total=%r",
                scraped.provider, key, value, scraped.total_time,
            )
            continue
        kept[key] = value
    if len(kept) >= 2 and total is not None and all(
        parse_duration(value) == total for value in kept.values()
    ):
        logger.info("Segments tous égaux au total écartés (%s) : %r", scraped.provider, kept)
        return {}
    return kept


# `fullmatch`, et non le `search` de `app.scrapers.utils.to_seconds` : cette dernière
# rend 900 sur « 0-2:-15:00 » (elle n'ancre qu'à droite) et 3825 sur « 01:23:45.6 »,
# là où l'écran rejette les deux (`secondsFromHms`, garde posée par #472). Réutiliser
# `to_seconds` ferait donc évaluer ici des lignes que l'écran affiche « — ⚠ ».
_DURATION = re.compile(r"(?:(?P<hours>\d+):)?(?P<minutes>\d{1,2}):(?P<seconds>\d{2})")


def parse_duration(value: str | None) -> int | None:
    """Secondes d'un `HH:MM:SS` ou `MM:SS`, `None` si ce n'est pas une durée."""
    if not isinstance(value, str):
        return None
    match = _DURATION.fullmatch(value.strip())
    if not match:
        return None
    minutes = int(match["minutes"])
    seconds = int(match["seconds"])
    if minutes >= 60 or seconds >= 60:
        return None
    return int(match["hours"] or 0) * 3600 + minutes * 60 + seconds


def total_time(scraped: ScrapedResult) -> str | None:
    """Temps total stockable : une durée lisible, sinon `None` (#969).

    Un libellé (« Abandon ») ou un format que `normalize_time` n'a pas su lire
    n'est pas un temps d'arrivée : le stocker en ferait un finisher.
    """
    if not scraped.total_time:
        return None
    if parse_duration(scraped.total_time) is None:
        logger.warning("Temps total écarté (%s) : %r", scraped.provider, scraped.total_time)
        return None
    return scraped.total_time


def derive_status(scraped: ScrapedResult) -> str:
    """Statut sportif. Respecte le statut explicite du scraper s'il existe,
    sinon retombe sur l'heuristique (finisher si temps total lisible, sinon DNF)."""
    if scraped.status:
        return scraped.status
    return STATUS_FINISHER if parse_duration(scraped.total_time) is not None else STATUS_DNF


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
        format_label=scraped.format_label or None,
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


def athlete_creation_fields(scraped: ScrapedResult) -> dict:
    """Champs de création d'un athlète neuf — mêmes règles que la branche de
    création d'`athlete_repository.resolve` (#706, résolution par lot :
    `_Persister` crée les athlètes manquants via `athlete_repository.create_batch`
    plutôt que ligne à ligne, mais doit leur poser exactement les mêmes champs)."""
    return {
        "nom": (scraped.athlete_name or "").strip(),
        "prenom": (scraped.athlete_firstname or "").strip(),
        "gender": scraped.gender,  # `ScrapedResult.gender` est typé `str = ""` (#1108)
        "birth_date": None,
        "club": scraped.club or None,
    }


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
        "total_time": total_time(scraped),
        "status": derive_status(scraped),
        "splits": build_splits(scraped) or None,
        "raw_data": scraped.raw_data or None,
        "team_name": scraped.team_name or None,
        "evidence_url": scraped.evidence_url or None,
        "is_pending_validation": scraped.is_pending_validation,
    }
