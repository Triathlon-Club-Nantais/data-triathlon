"""
nextrun.fr : API JSON publique derrière la page de résultats SvelteKit (#1224).

    scrape_event_all(url)
      ├─ GET /api/events/{event}/editions/{edition}/results → courses de l'édition
      └─ GET /api/races/{race_id}/results/rows?page=N        → une ligne par personne

Un duo publie chaque équipier sur sa ligne (dossard, temps et rang propres) :
on les importe tels quels, comme runnerbreizh. Détail et mesures :
`docs/scrapers/nextrun.md`.
"""
import re
from datetime import date, datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from app.core import http

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER, ScrapedResult
from .classify import classify_event_type
from .utils import (
    DEFAULT_HEADERS,
    anonymous_identity,
    derive_status_from_label,
    fmt_seconds,
    heat_is_relay,
    qualify_event_name,
)

API = "https://nextrun.fr/api"
# Valeurs admises par la source : 20, 50, 100, 200 (422 au-delà).
PAGE_SIZE = 200
_MAX_PAGES = 50
_RE_EDITION = re.compile(r"/events/([^/]+)/editions/([^/]+)")
# Type de licence (177 lignes sur 306 à Lancieux 2026), pas un club.
_NOT_A_CLUB = {"licence expérience"}
_GENDERS = {"male": "M", "female": "F"}
_PARIS = ZoneInfo("Europe/Paris")


def _local_date(value: str | None) -> date | None:
    """La source date en UTC : `2026-08-21T22:00:00Z` est le 22/08 à Lancieux."""
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(_PARIS).date()


def _status(row: dict) -> str:
    label = (row.get("status") or "").strip()
    return STATUS_FINISHER if label.lower() == "finisher" else derive_status_from_label(label)


def _result(
    row: dict, *, url: str, event_name: str, event_date: date | None, event_type: str,
    is_relay: bool, race_id: str,
) -> ScrapedResult:
    bib = str(row.get("bib_number") or "").strip()
    name, firstname = anonymous_identity(
        (row.get("last_name") or "").strip(), (row.get("first_name") or "").strip(),
        bib=bib, scope=race_id,
    )
    club = (row.get("club") or "").strip()
    time_ms = row.get("official_time_ms") or row.get("real_time_ms")
    result = ScrapedResult(
        source_url=url,
        provider="nextrun",
        athlete_name=name,
        athlete_firstname=firstname,
        club="" if club.lower() in _NOT_A_CLUB else club,
        category=(row.get("category") or "").strip(),
        gender=_GENDERS.get(row.get("gender") or "", ""),
        bib_number=bib,
        event_name=event_name,
        event_date=event_date,
        event_type=event_type,
        rank_overall=row.get("scratch_rank"),
        rank_gender=row.get("gender_rank"),
        rank_category=row.get("category_rank"),
        total_time=fmt_seconds(time_ms // 1000) if time_ms else "",
        is_relay=is_relay,
        status=_status(row),
        raw_data=dict(row),
    )
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.total_time = ""
        result.rank_overall = result.rank_gender = result.rank_category = None
    return result


def _rows(client, race_id: str) -> list[dict]:
    """Toutes les lignes d'une course, pages suivies jusqu'au `total` annoncé, ou
    tant qu'elles sont pleines si la source ne l'annonce pas."""
    rows: list[dict] = []
    for page in range(1, _MAX_PAGES + 1):
        response = client.get(
            f"{API}/races/{race_id}/results/rows", params={"page": page, "page_size": PAGE_SIZE},
        )
        response.raise_for_status()
        payload = response.json()
        batch = payload.get("rows") or []
        rows.extend(batch)
        total = payload.get("total")
        if not batch or (len(rows) >= total if total else len(batch) < PAGE_SIZE):
            return rows
    # Rendre un classement tronqué le figerait dans le cache.
    raise ValueError(f"Pagination nextrun interrompue après {_MAX_PAGES} pages (course {race_id}).")


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Tous les participants des courses publiées de l'édition visée par l'URL."""
    match = _RE_EDITION.search(urlparse(url).path)
    if not match:
        raise ValueError(
            f"URL nextrun sans édition : {url} (forme attendue "
            "https://nextrun.fr/events/<épreuve>/editions/<édition>/results)."
        )
    event_slug, edition_slug = match.groups()
    results: list[ScrapedResult] = []
    with http.client(timeout=30, headers=DEFAULT_HEADERS) as client:
        response = client.get(f"{API}/events/{event_slug}/editions/{edition_slug}/results")
        response.raise_for_status()
        edition = response.json()
        event_name = (edition.get("event_name") or "").strip()
        for race in edition.get("races") or []:
            if not race.get("results_published"):
                continue
            race_name = (race.get("name") or "").strip()
            context = {
                "url": url,
                "event_name": qualify_event_name(event_name, race_name),
                "event_date": _local_date(race.get("date") or edition.get("start_date")),
                "event_type": classify_event_type(race_name, contexte=event_name),
                "is_relay": heat_is_relay(race_name),
                "race_id": race["race_id"],
            }
            results.extend(_result(row, **context) for row in _rows(client, race["race_id"]))
    return results
