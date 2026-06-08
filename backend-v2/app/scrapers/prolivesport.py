"""
Scraper for prolivesport.fr

URL format:
  https://www.prolivesport.fr/index.php?chap=event&sub=liveV3&eventId=979&race=Triathlon%20M
    &search=ARNOUX

API base: https://api.prolivesport.fr/apiws
Token:    AUTH_PLSWS_V2  (hardcoded in the Angular bundle)

Flow:
  1. Parse eventId + race from URL
  2. GET /result/raceList/{eventId}/  → verify race exists
  3. GET /result/indiv/{eventId}/{race}/  → all athletes (JSON)
  4. Filter by lastname (search param)
  5. GET /result/splitDetail/{eventId}/  → field→split label mapping
  6. Map T1-T5 fields to swim/T1/bike/T2/run
"""
import re
from datetime import date
from urllib.parse import parse_qs, urlparse

import httpx

from .base import (
    STATUS_DNF,
    STATUS_DNS,
    STATUS_DSQ,
    STATUS_FINISHER,
    ScrapedResult,
)
from .utils import normalize_rank, normalize_time

API_BASE = "https://api.prolivesport.fr/apiws"
TOKEN = "AUTH_PLSWS_V2"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "access-token": TOKEN,
    "Accept": "application/json",
}

# Labels → split field mapping
_SWIM_LABELS = {"swim", "nat", "cat/nat", "natation"}
_T1_LABELS   = {"#1", "t1", "trans1", "transition1"}
_BIKE_LABELS  = {"bike", "velo", "vélo", "cycle", "bikestart"}
_T2_LABELS   = {"#2", "t2", "trans2", "transition2"}
_RUN_LABELS  = {"run", "cap", "course", "courseapied", "c.a.p"}


def _build_split_map(splits: list, race: str) -> dict[str, str]:
    """
    Build {field_name: split_role} from the splitDetail API response.
    split_role in: swim, t1, bike, t2, run
    """
    mapping: dict[str, str] = {}
    for s in splits:
        if s.get("race", "").lower() != race.lower():
            continue
        field = s.get("field", "")
        label = re.sub(r"\s+", "", (s.get("label") or s.get("displayTitle") or "")).lower()
        if any(lbl in label for lbl in _SWIM_LABELS):
            mapping[field] = "swim"
        elif any(lbl == label for lbl in _T1_LABELS):
            mapping[field] = "t1"
        elif any(lbl in label for lbl in _BIKE_LABELS):
            mapping[field] = "bike"
        elif any(lbl == label for lbl in _T2_LABELS):
            mapping[field] = "t2"
        elif any(lbl in label for lbl in _RUN_LABELS):
            mapping[field] = "run"
    return mapping


def _parse_athlete(athlete: dict, split_map: dict, url: str, event_name: str, event_type: str, event_date) -> ScrapedResult:
    result = ScrapedResult(source_url=url, provider="prolivesport")
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date

    result.athlete_name = athlete.get("lastname", "").strip().upper()
    result.athlete_firstname = athlete.get("firstname", "").strip()
    result.bib_number = athlete.get("number", "")
    result.club = athlete.get("club", "")
    result.category = athlete.get("categoryRef", athlete.get("category", ""))
    result.gender = athlete.get("sex", "")
    result.rank_overall = normalize_rank(athlete.get("rank"))
    result.rank_gender = normalize_rank(athlete.get("rankSex"))
    result.rank_category = normalize_rank(athlete.get("rankCat"))
    result.total_time = normalize_time(athlete.get("time", ""))

    # Extract splits using the field→role mapping
    for field, role in split_map.items():
        t = normalize_time(athlete.get(f"time{field}", ""))
        if not t or t == "00:00:00":
            continue
        if role == "swim" and not result.swim_time:
            result.swim_time = t
        elif role == "t1" and not result.t1_time:
            result.t1_time = t
        elif role == "bike" and not result.bike_time:
            result.bike_time = t
        elif role == "t2" and not result.t2_time:
            result.t2_time = t
        elif role == "run" and not result.run_time:
            result.run_time = t

    result.raw_data = {k: v for k, v in athlete.items() if not k.isdigit()}
    return result


def _fetch_indiv(event_id: str, race: str, client: httpx.Client) -> list[dict]:
    r = client.get(f"{API_BASE}/result/indiv/{event_id}/{race}/", timeout=20)
    r.raise_for_status()
    data = r.json()
    if not data.get("success"):
        raise ValueError(f"Prolivesport API erreur pour event {event_id} / race {race}: {data.get('message')}")
    return data.get("result", [])


def _fetch_split_map(event_id: str, race: str, client: httpx.Client) -> dict[str, str]:
    r = client.get(f"{API_BASE}/result/splitDetail/{event_id}/", timeout=15)
    r.raise_for_status()
    splits = r.json().get("result", [])
    return _build_split_map(splits, race)


def _fetch_event_meta(event_id: str, client: httpx.Client) -> tuple[str, date | None]:
    """Return (event_name, event_date)."""
    r = client.get(f"{API_BASE}/event/detail/{event_id}/", timeout=15)
    r.raise_for_status()
    result = r.json().get("result", [{}])
    ev = result[0] if result else {}
    name = ev.get("eventName", "")
    raw_date = ev.get("eventDateStart", "")
    event_date = None
    if raw_date and raw_date[:4] != "0000":
        try:
            event_date = date.fromisoformat(raw_date[:10])
        except ValueError:
            pass
    return name, event_date


def _detect_event_type(race: str) -> str:
    race_l = race.lower()
    if "duathlon" in race_l:
        if any(x in race_l for x in ["xs", "extra"]):
            return "duathlon-xs"
        if "-s" in race_l or " s" in race_l:
            return "duathlon-s"
        if "-m" in race_l or " m" in race_l:
            return "duathlon-m"
        if "-l" in race_l or " l" in race_l:
            return "duathlon-l"
        return "duathlon"
    if "swimrun" in race_l or "swim run" in race_l:
        return "swimrun"
    if "aquathlon" in race_l:
        return "aquathlon"
    if "bike" in race_l and "run" in race_l:
        return "bike-run"
    if "triathlon" in race_l or "tri" in race_l:
        if "xs" in race_l:
            return "triathlon-xs"
        if "-s" in race_l or " s" in race_l or race_l.endswith(" s"):
            return "triathlon-s"
        if "-m" in race_l or " m" in race_l or race_l.endswith(" m"):
            return "triathlon-m"
        if "-l" in race_l or " l" in race_l or race_l.endswith(" l"):
            return "triathlon-l"
        if "xl" in race_l:
            return "triathlon-xl"
        return "triathlon"
    return "triathlon"


def _parse_url(url: str) -> tuple[str, str]:
    """
    Extrait (event_id, race) d'une URL prolivesport. Deux formes gérées :
      - query : `?eventId=1082&race=S`
      - front : `/result/{eventId}/{race}` où race est un index positionnel
        (ex. `6`) ou un code (ex. `S`).
    `race` peut être vide → 1ʳᵉ course par défaut (résolu plus tard).
    """
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    event_id = params.get("eventId", [""])[0]
    race = params.get("race", [""])[0].strip()

    if not event_id:
        # Forme front /result/{eventId}/{race}
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if "result" in parts:
            rest = parts[parts.index("result") + 1:]
            event_id = rest[0] if rest else ""
            race = rest[1] if len(rest) >= 2 else race

    if not event_id:
        raise ValueError("URL prolivesport.fr sans identifiant d'événement.")
    return event_id, race


def _resolve_race(race: str, races: list[dict]) -> str:
    """
    Résout le token `race` en code de course :
      - vide → 1ʳᵉ course de la liste
      - numérique → index positionnel (0-based) dans `races`
      - sinon → code course tel quel
    """
    if not race:
        if not races:
            raise ValueError("Aucune course disponible pour cet événement.")
        return races[0].get("race", "")
    if race.isdigit():
        idx = int(race)
        if not 0 <= idx < len(races):
            raise ValueError(
                f"Index de course {idx} hors limites ({len(races)} courses)."
            )
        return races[idx].get("race", "")
    return race


def _derive_status(athlete: dict) -> str:
    """Statut sportif d'un athlète prolivesport, lu des champs distincts de l'API.

    Le champ `dns` est ignoré car non fiable (`dns="O"` est posé sur des
    finishers) ; on déduit DNS de l'absence de temps réel.
    """
    if (athlete.get("dsq") or "").strip().upper() == "O":
        return STATUS_DSQ
    if (athlete.get("dnf") or "").strip().upper() == "O":
        return STATUS_DNF
    t = (athlete.get("time") or "").strip()
    if t and t != "00:00:00":
        return STATUS_FINISHER
    return STATUS_DNS


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Fetch all participants for a Prolivesport event/race."""
    event_id, race_token = _parse_url(url)

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        event_name, event_date = _fetch_event_meta(event_id, client)
        r = client.get(f"{API_BASE}/result/raceList/{event_id}/", timeout=15)
        races = r.json().get("result", [])
        race = _resolve_race(race_token, races)
        if not race:
            raise ValueError(
                f"Aucune épreuve trouvée pour l'événement prolivesport {event_id}."
            )

        event_type = _detect_event_type(race)
        athletes = _fetch_indiv(event_id, race, client)
        split_map = _fetch_split_map(event_id, race, client)

    return [
        _parse_athlete(a, split_map, url, event_name, event_type, event_date)
        for a in athletes
        if _derive_status(a) == STATUS_FINISHER
    ]
