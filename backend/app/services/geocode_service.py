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
from datetime import timedelta

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


def extract_city(event_name: str) -> str:
    """Extrait une ville/localité cherchable depuis un nom d'épreuve triathlon français."""
    name = event_name.strip()
    name = re.sub(r"\b(20\d{2}|[0-9]+e?\s+edition)\b", "", name, flags=re.I).strip()
    name = re.sub(r"[-–—]+$", "", name).strip()

    prefixes = (
        r"(triathlon|tri|duathlon|swimrun|swim[- ]?run|aquathlon|aquarun|bike[- ]?run"
        r"|run[- ]?bike|challenge|ironman|half|ultra|trail)\s+"
        r"(de\s+la\s+|de\s+le\s+|des\s+|de\s+|du\s+|d'\s*|d’\s*|international\s+)?"
        r"(la\s+|le\s+|les\s+|saint[-\s]|sainte[-\s])?"
    )
    cleaned = re.sub(prefixes, "", name, flags=re.I).strip()
    cleaned = re.sub(
        r"\s+(s|m|l|xl|xs|xxl|sprint|olympique|olympic|half|longue|distance|format)\s*$",
        "", cleaned, flags=re.I,
    ).strip()
    cleaned = re.sub(r"\b\d+[\s\-]?(plages?|km|h)\b", "", cleaned, flags=re.I).strip()
    cleaned = re.split(r"\s+[àa]\s+|\s+[-–]\s+", cleaned)[0].strip()
    return cleaned or event_name


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
                params={"q": query, "format": "json", "limit": 5, "countrycodes": "fr"},
                headers={"User-Agent": settings.geocode_user_agent},
            )
        results = r.json()
        time.sleep(settings.geocode_min_interval_seconds)  # rate limit Nominatim
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

    try:
        for index, course in enumerate(courses):
            coord = geocode(course.name)
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
    except KeyboardInterrupt:
        outcome.interrupted = True

    return outcome
