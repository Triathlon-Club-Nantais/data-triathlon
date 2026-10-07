"""
Géocodage des épreuves via Nominatim (OpenStreetMap).

Extraction de la ville depuis le nom d'épreuve français, puis recherche Nominatim
avec cache mémoire et respect du rate-limit (1 req/s).

`run_geocode_courses` (#579) est le seul point d'écriture de
`Course.latitude`/`longitude`/`geocoded_at` : hors ligne, via
`python -m app.cli geocode-courses`, jamais dans une route. `GET
/stats/events-geo` ne fait plus qu'un `SELECT` sur ces colonnes.
"""
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core import http
from app.core.config import get_settings
from app.core.time import utcnow
from app.repositories import course_repository
from app.services.batch import BatchFailure, est_echec_total

logger = logging.getLogger(__name__)

#: Délai avant de retenter un échec (#579). Une épreuve que Nominatim ne sait
#: pas géocoder a de fortes chances de ne toujours pas l'être le lendemain, et
#: chaque tentative coûte jusqu'à 2,2 s (deux recherches, cf. `geocode`) : une
#: semaine borne le nombre de tentatives sans figer un échec pour toujours —
#: une correction du nom d'épreuve ou de l'extraction de ville finit par être
#: retentée.
RETRY_APRES = timedelta(days=7)

# Cache mémoire (réinitialisé au redémarrage du serveur)
_geo_cache: dict[str, tuple[float, float] | None] = {}


#: Rectangle de la France métropolitaine, Corse comprise (`ouest,nord,est,sud`) :
#: `countrycodes=fr` couvre l'outre-mer, et « AT BAIN » tombait en Guadeloupe (#1203).
_OUEST, _NORD, _EST, _SUD = -5.3, 51.2, 9.7, 41.2
VIEWBOX_METROPOLE = f"{_OUEST},{_NORD},{_EST},{_SUD}"

#: Sponsors collés à la ville dans des noms réels (#1203).
_SPONSORS = re.compile(r"\b(audencia)\s+", re.I)


def extract_city(event_name: str) -> str:
    """Extrait une ville/localité cherchable depuis un nom d'épreuve triathlon français."""
    name = event_name.strip()
    # Ordinal d'édition en tête (« 35ème Triathlon de Laval », « 9e édition du… »),
    # qui empêchait le retrait du préfixe de discipline (#1203).
    name = re.sub(
        r"^\d+\s*(?:e|è|ème|eme|er|ère)\b\s*(?:[ée]dition\s+(?:du|de\s+la|de|des)\s+)?",
        "", name, flags=re.I,
    ).strip()
    name = _SPONSORS.sub("", name)
    name = re.sub(r"\b(20\d{2}|\d+\s*(?:e|è|ème|eme)?\s+[ée]dition)(?!\w)", "", name, flags=re.I).strip()
    name = re.sub(r"[-–—]+$", "", name).strip()
    # Suffixe de heat (« … 2025 - Triathlon M ») coupé avant tout autre nettoyage.
    name = re.split(r"\s+[-–]\s+|\s+[-–]$", name)[0].strip()

    prefixes = (
        r"(triathlon|tri|duathlon|swimrun|swim[- ]?run|aquathlon|aquarun|bike[- ]?run"
        r"|run[- ]?bike|challenge|ironman|half|ultra|trail)\s+"
        r"(de\s+la\s+|de\s+le\s+|des\s+|de\s+|du\s+|d'\s*|d’\s*|international\s+)?"
        r"(saint[-\s]|sainte[-\s])?"
    )
    cleaned = re.sub(prefixes, "", name, flags=re.I).strip()
    cleaned = re.sub(r"^pays\s+(?:de\s+la\s+|de\s+|du\s+|des\s+|d['’]\s*)", "", cleaned, flags=re.I).strip()
    cleaned = re.sub(
        r"\s+(s|m|l|xl|xs|xxl|sprint|olympique|olympic|half|longue|distance|format)\s*$",
        "", cleaned, flags=re.I,
    ).strip()
    cleaned = re.sub(r"\b\d+[\s\-]?(plages?|km|h)\b", "", cleaned, flags=re.I).strip()
    cleaned = re.split(r"\s+[àa]\s+|\s+[-–]\s+", cleaned)[0].strip()
    return cleaned or event_name


def event_stem(name: str) -> str:
    """Nom de l'événement, sans le suffixe de heat (« Triathlon de Carnac 2025 - Triathlon M »)."""
    return re.split(r"\s+[-–]\s+", name.strip())[0]


def _nominatim_search(query: str) -> tuple[float, float] | None:
    """Un appel Nominatim ; renvoie (lat, lon) du résultat le plus pertinent, ou None."""
    settings = get_settings()
    try:
        # L'appel d'origine était un httpx.get nu (follow_redirects=False par
        # défaut en httpx) : surcharge du défaut de la fabrique pour ne rien
        # changer d'observable à ce site.
        with http.client(timeout=5, follow_redirects=False) as client:
            r = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query, "format": "json", "limit": 5, "countrycodes": "fr",
                    "viewbox": VIEWBOX_METROPOLE, "bounded": 1,
                },
                headers={"User-Agent": settings.geocode_user_agent},
            )
        results = r.json()
        time.sleep(settings.geocode_min_interval_seconds)  # rate limit Nominatim
        # Filet derrière `bounded=1` : un résultat d'outre-mer n'est jamais retenu (#1203).
        results = [
            x for x in results
            if _SUD <= float(x["lat"]) <= _NORD and _OUEST <= float(x["lon"]) <= _EST
        ]
        places = [
            x for x in results if x.get("class") in ("place", "boundary", "administrative")
        ]
        hits = places or results
        if hits:
            hits.sort(key=lambda x: float(x.get("importance", 0)), reverse=True)
            return (float(hits[0]["lat"]), float(hits[0]["lon"]))
    except Exception as exc:
        logger.warning("Géocodage échoué pour « %s » : %s", query, exc)
    return None


def geocode(event_name: str) -> tuple[float, float] | None:
    """Géocode un nom d'épreuve en (lat, lon). Résultat mis en cache mémoire."""
    if event_name in _geo_cache:
        return _geo_cache[event_name]

    city = extract_city(event_name)
    if not city or len(city) < 3:
        _geo_cache[event_name] = None
        return None

    coord = _nominatim_search(f"{city}, France")
    if coord is None and city.lower() != event_name.lower():
        coord = _nominatim_search(f"{event_name}, France")

    _geo_cache[event_name] = coord
    return coord


@dataclass
class GeocodeOutcome:
    """Bilan d'un `geocode-courses`. `total`/`geocoded`/`errors` comptent des épreuves.

    `processed` n'est distinct de `total` que sous Ctrl-C (bilan partiel), sur
    le patron de `RescrapeOutcome`.
    """
    total: int = 0
    geocoded: int = 0
    errors: int = 0
    processed: int = 0
    interrupted: bool = False
    dry_run: bool = False
    #: Épreuves ciblées, listées sans appel Nominatim (`--dry-run` seulement).
    dry_run_names: list[str] = field(default_factory=list)
    #: Épreuves fautives (ville introuvable), pour le détail du rapport.
    failures: list[BatchFailure] = field(default_factory=list)

    @property
    def echec_total(self) -> bool:
        """Toutes les épreuves ciblées ont échoué (cf. `batch.est_echec_total`).

        Propriété, pas champ : `asdict()` ne sérialise que les champs, la
        charge `--json` reste inchangée. Un dry-run n'appelle jamais Nominatim,
        il ne peut donc jamais être un échec.
        """
        if self.dry_run:
            return False
        return est_echec_total(epreuves=self.total, errors=self.errors)


def run_geocode_courses(
    db: Session,
    *,
    limit: int | None = None,
    retry_after: timedelta = RETRY_APRES,
    dry_run: bool = False,
    on_item: Callable[[int, int, str, tuple[float, float] | None], None] | None = None,
) -> GeocodeOutcome:
    """Géocode les épreuves qui n'ont pas encore de coordonnées (#579).

    Sort Nominatim du chemin de requête : c'est la **seule** écriture de
    `Course.latitude`/`longitude`/`geocoded_at`, appelée hors ligne par la
    commande `geocode-courses` — jamais par l'import (web ou CLI), qui sert
    aussi le flux SSE synchrone du site public et ne doit rien ajouter à son
    temps de réponse.

    Chaque épreuve est commitée séparément
    (`course_repository.save_geocode_attempt`) : un Ctrl-C au milieu du lot ne
    perd pas le travail déjà fait, seule la tentative en cours l'est.
    `on_item`, s'il est fourni, est notifié après chaque tentative — la CLI
    l'utilise pour afficher la progression sur stderr.
    """
    cutoff = utcnow() - retry_after
    courses = course_repository.list_missing_geocode(db, retry_after=cutoff, limit=limit)
    outcome = GeocodeOutcome(total=len(courses), dry_run=dry_run)

    if dry_run:
        outcome.dry_run_names = [c.name for c in courses]
        return outcome

    # Une recherche par événement, propagée à ses heats (#1203). L'URL ne
    # regroupe pas : elle diffère d'un heat à l'autre (`?heat=`, `?parcours=`,
    # un id par heat chez sportinnovation) ; le nom avant « - » et la date, si.
    events: dict[tuple[str, date | None], list] = {}
    for course in courses:
        stem = event_stem(course.name)
        events.setdefault((stem.casefold(), course.event_date), []).append(course)

    index = 0
    try:
        for heats in events.values():
            coord = geocode(event_stem(heats[0].name))
            for course in heats:
                course_repository.save_geocode_attempt(db, course, coord)
                outcome.processed += 1
                if coord is not None:
                    outcome.geocoded += 1
                else:
                    outcome.errors += 1
                    outcome.failures.append(
                        BatchFailure(url=course.name, label=course.name, message="ville introuvable")
                    )
                if on_item is not None:
                    on_item(index, outcome.total, course.name, coord)
                index += 1
    except KeyboardInterrupt:
        outcome.interrupted = True

    return outcome
