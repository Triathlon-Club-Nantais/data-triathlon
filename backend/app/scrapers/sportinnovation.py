"""
Scraper for sportinnovation.fr

Two URL formats:

1. www.sportinnovation.fr/Evenements/Resultats/{eventId}  (28/32 URLs)
   - Server-rendered HTML table with full splits
   - GET all rows, filter by name in Python
   - Name cell format: "LASTNAME FirstnameG-CatG" (G=H/F, Cat=category)
   - Columns: Place | Dossard | Nom | Place Cat. | Club | Temps | ... | Tps Nat | T1 | Tps Velo | T2 | Tps CAP

2. results.sportinnovation.fr/race/{slug}  (format 2026)
   - JSON API : GET /api/races/{slug} → meta, /api/races/{slug}/results → athlètes
   - Splits via GET /api/results/{id_or_slug}?intermediates=1 par athlète
   - Récupérés en parallèle (ThreadPoolExecutor, max 20 workers)

3. results.sportinnovation.fr/detail/{id}  (lien individuel)
   - Résout le raceSlug via GET /api/results/{id}, puis même pipeline que /race/{slug}
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from .base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, ScrapedResult
from .utils import derive_status_from_label, normalize_rank, normalize_time

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
}
API_BASE = "https://sportinnovation.fr/api"


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — HTML format (www.sportinnovation.fr)
# ──────────────────────────────────────────────────────────────────────────────

_NAME_RE = re.compile(
    r"^(?P<lastname>[A-ZÀ-Ÿ][A-ZÀ-Ÿ'\- ]+?)\s+(?P<firstname>[A-Za-zÀ-ÿ'\- ]+?)(?P<gender>[HF])-(?P<cat>[A-Z0-9]+)(?P<gender2>[HF])?$"
)


def _parse_name_cell(raw: str) -> tuple[str, str, str, str]:
    """
    Parse "GUEGANO JordanH-S3H" → (lastname, firstname, gender, category).
    Falls back gracefully when format doesn't match.
    """
    raw = raw.strip()
    m = _NAME_RE.match(raw)
    if m:
        return (
            m.group("lastname").strip(),
            m.group("firstname").strip(),
            m.group("gender"),
            m.group("cat"),
        )
    # Fallback: split on last uppercase run
    parts = raw.split()
    # Find where uppercase run ends
    i = 0
    while i < len(parts) and parts[i].replace("-", "").replace("'", "").isupper():
        i += 1
    lastname = " ".join(parts[:i]) if i > 0 else raw
    rest = " ".join(parts[i:]) if i < len(parts) else ""
    # Extract gender/cat suffix from rest
    gcat = re.search(r"([HF])-([A-Z0-9]+)", rest)
    if gcat:
        firstname = rest[: gcat.start()].strip()
        gender = gcat.group(1)
        cat = gcat.group(2)
    else:
        firstname = rest
        gender = ""
        cat = ""
    return lastname, firstname, gender, cat


def _detect_event_type(race_name: str) -> str:
    from app.scrapers.classify import classify_event_type
    return classify_event_type(race_name)


def _col_indices(headers: list[str]) -> dict[str, int]:
    """Map column role → index from the <th> header row."""
    mapping = {}
    for i, h in enumerate(headers):
        hl = h.lower().strip()
        if "place" == hl or "rang" == hl:
            mapping.setdefault("rank_overall", i)
        elif "dossard" in hl or "bib" in hl:
            mapping.setdefault("bib", i)
        elif "nom" == hl or "athlete" in hl or "nom /" in hl:
            mapping.setdefault("name", i)
        elif "place cat" in hl or "cat." in hl:
            mapping.setdefault("rank_cat", i)
        elif "club" in hl or "équipe" in hl or "equipe" in hl:
            mapping.setdefault("club", i)
        elif "tps off" in hl or "temps off" in hl:
            mapping.setdefault("total_time", i)
        elif "nat" in hl or "swim" in hl or "nage" in hl:
            mapping.setdefault("swim_time", i)
        elif "transition 1" in hl or "t1" == hl:
            mapping.setdefault("t1_time", i)
        elif "velo" in hl or "vélo" in hl or "bike" in hl or "cycle" in hl:
            mapping.setdefault("bike_time", i)
        elif "transition 2" in hl or "t2" == hl:
            mapping.setdefault("t2_time", i)
        elif "cap" in hl or "run" in hl or "course" in hl or "corse" in hl:
            mapping.setdefault("run_time", i)
    # Fallback: use Temps Officiel if no Tps Off.
    if "total_time" not in mapping:
        for i, h in enumerate(headers):
            if "temps" in h.lower():
                mapping["total_time"] = i
                break
    return mapping


def _parse_html_row(tds: list[str], col: dict[str, int], url: str, race_name: str) -> ScrapedResult:
    result = ScrapedResult(source_url=url, provider="sportinnovation")
    result.event_name = race_name
    result.event_type = _detect_event_type(race_name)

    def get(key: str) -> str:
        idx = col.get(key)
        return tds[idx].strip() if idx is not None and idx < len(tds) else ""

    raw_name = get("name")
    lastname, firstname, gender, cat = _parse_name_cell(raw_name)
    result.athlete_name = lastname
    result.athlete_firstname = firstname
    result.gender = gender
    result.category = cat

    result.bib_number = get("bib")
    result.club = get("club")
    result.rank_overall = normalize_rank(get("rank_overall"))
    result.rank_category = normalize_rank(get("rank_cat"))
    raw_total = get("total_time")
    status = derive_status_from_label(raw_total)
    if status:
        result.status = status
    else:
        result.total_time = normalize_time(raw_total)
    result.swim_time = normalize_time(get("swim_time"))
    result.t1_time = normalize_time(get("t1_time"))
    result.bike_time = normalize_time(get("bike_time"))
    result.t2_time = normalize_time(get("t2_time"))
    result.run_time = normalize_time(get("run_time"))
    if result.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        result.rank_overall = None
        result.rank_category = None
        result.rank_gender = None
    result.raw_data = {"col_map": col}
    return result


def _fetch_html_results(
    event_id: str,
    client: httpx.Client,
    search: str = "",
    page: int = 1,
) -> tuple[str, list[list[str]], dict[str, int]]:
    """
    Fetch result rows from the HTML page.

    With search="": POST with empty search + numPage, returns rows for the race.
    With search=NAME: POST dossardSearch=NAME (server-side filter across all races).
    Returns (race_name, rows, col_indices).
    """
    url = f"https://sportinnovation.fr/Evenements/Resultats/{event_id}"

    resp = client.post(
        url,
        data={"dossardSearch": search, "numPage": str(page), "sexSearch": ""},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    # Race name from og:title "Résultats : Triathlon M"
    race_name = ""
    og = soup.find("meta", property="og:title")
    if og and og.get("content"):
        race_name = og["content"].replace("Résultats :", "").replace("Résultats:", "").strip()
    if not race_name:
        h1 = soup.find("h1")
        race_name = h1.get_text(strip=True) if h1 else ""

    # Parse table headers
    th_row = soup.select_one("thead tr") or soup.select_one("tr")
    headers = [th.get_text(strip=True) for th in (th_row.select("th") if th_row else [])]
    col = _col_indices(headers)

    rows_data = []
    for tr in soup.select("tbody tr"):
        tds = [td.get_text(strip=True) for td in tr.select("td")]
        if tds:
            rows_data.append(tds)

    return race_name, rows_data, col


def _fetch_all_pages(event_id: str, client: httpx.Client) -> tuple[str, list[list[str]], dict[str, int]]:
    """Fetch all paginated rows for a race (250 rows per page)."""
    all_rows: list[list[str]] = []
    race_name = ""
    col: dict[str, int] = {}
    PAGE_SIZE = 250

    for page in range(1, 20):  # safety cap at 20 pages = 5000 participants
        rn, rows, c = _fetch_html_results(event_id, client, search="", page=page)
        if not race_name:
            race_name, col = rn, c
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < PAGE_SIZE:
            break  # last page

    return race_name, all_rows, col


def _classify_results_url(url: str) -> tuple[str, str]:
    """
    Classe une URL results.sportinnovation.fr :
      - /race/{slug}    → ("race", slug)    [affichage 2026, niveau course]
      - /detail/{id}    → ("detail", id)    [lien individuel → résout le raceSlug]
      - /{codeUrl}      → ("event", codeUrl) [niveau événement]
    """
    parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    if not parts:
        raise ValueError(f"URL results.sportinnovation.fr sans identifiant : {url}")
    if parts[0] == "race" and len(parts) >= 2:
        return "race", parts[1]
    if parts[0] == "detail" and len(parts) >= 2:
        return "detail", parts[1]
    return "event", parts[0]


def _parse_api_athlete(
    a: dict,
    url: str,
    event_name: str,
    event_type: str,
    event_date,
    splits: dict[str, str] | None = None,
) -> ScrapedResult:
    """Construit un ScrapedResult depuis un athlète de l'API JSON sportinnovation."""
    res = ScrapedResult(source_url=url, provider="sportinnovation")
    res.event_name = event_name
    res.event_type = event_type
    res.event_date = event_date
    res.athlete_name = (a.get("lastName") or "").strip().upper()
    res.athlete_firstname = (a.get("firstName") or "").strip()
    res.bib_number = str(a.get("bib") or "")
    res.club = (a.get("clubName") or "").strip()
    res.gender = a.get("sex") or ""
    res.category = a.get("category") or ""
    res.rank_overall = normalize_rank(str(a.get("generalRanking") or ""))
    res.rank_gender = normalize_rank(str(a.get("sexRanking") or ""))
    res.rank_category = normalize_rank(str(a.get("categoryRanking") or ""))
    res.status = derive_status_from_label(str(a.get("status") or a.get("state") or ""))
    if res.status in (STATUS_DNF, STATUS_DNS, STATUS_DSQ):
        res.total_time = ""
        res.rank_overall = res.rank_gender = res.rank_category = None
    else:
        res.total_time = normalize_time(a.get("officialTime") or a.get("realTime") or "")
    if splits:
        res.swim_time = splits.get("swim", "")
        res.t1_time = splits.get("t1", "")
        res.bike_time = splits.get("bike", "")
        res.t2_time = splits.get("t2", "")
        res.run_time = splits.get("run", "")
    res.raw_data = a
    return res


def _fetch_event_meta_api(event_id, client: httpx.Client) -> tuple[str, date | None]:
    """Récupère (nom, date) d'un événement via /api/events/{id}."""
    ev = client.get(f"{API_BASE}/events/{event_id}", timeout=15).json()
    event_date = None
    raw = ev.get("eventDate", "")
    if raw:
        try:
            event_date = date.fromisoformat(raw[:10])
        except ValueError:
            pass
    return ev.get("title", ""), event_date


def _location_to_slot(location: str) -> str | None:
    """
    Traduit un nom de point intermédiaire sportinnovation en slot triathlon.

    Triathlon (labels français, ex. BayMan) :
      "Temps Natation" → swim, "Transition 1" → t1, "Temps Vélo" → bike,
      "Transition 2" → t2, "Temps CaP" → run

    Duathlon (labels checkpoints) :
      IN1 → swim (course1), OUT1 → t1, VELO1 → bike, OUT2 → t2, IN2 → run (course2)
      CAP*/START/FINISH ignorés (sous-checkpoints, non porteurs du temps de segment)
      (build_splits ré-étiquette swim/run → course1/course2 selon event_type)
    """
    loc = location.lower().strip()
    # Triathlon — labels français (Temps Natation, Transition 1, Temps Vélo…)
    if any(k in loc for k in ("natation", "swim", "nage")):
        return "swim"
    if "transition 1" in loc or loc == "t1":
        return "t1"
    if "transition 2" in loc or loc == "t2":
        return "t2"
    if any(k in loc for k in ("vélo", "velo", "bike", "cycle")):
        return "bike"
    if any(k in loc for k in ("temps cap", "temps cour", "course à pied")):
        return "run"
    # Duathlon — checkpoint labels exacts (évite de matcher CAP1/CAP2)
    if loc == "in1":
        return "swim"
    if loc == "out1":
        return "t1"
    if loc in ("velo1", "velo"):
        return "bike"
    if loc == "out2":
        return "t2"
    if loc == "in2":
        return "run"
    return None


def _intermediates_to_splits(intermediates: list[dict]) -> dict[str, str]:
    """Construit un dict slot→temps depuis la liste d'intermédiaires triés par position."""
    splits: dict[str, str] = {}
    sorted_inter = sorted(intermediates, key=lambda x: x.get("position") or 99)
    for inter in sorted_inter:
        slot = _location_to_slot(inter.get("location") or "")
        if not slot:
            continue
        t = normalize_time(inter.get("officialTime") or "")
        if t and slot not in splits:
            splits[slot] = t
    return splits


def _fetch_athlete_splits(athlete_ref: str | int) -> dict[str, str]:
    """Récupère les splits d'un athlète via /api/results/{ref}?intermediates=1.
    Crée son propre client httpx (thread-safe, pas de partage de connexion).
    """
    try:
        with httpx.Client(follow_redirects=True, timeout=15, headers=HEADERS) as c:
            r = c.get(
                f"{API_BASE}/results/{athlete_ref}",
                params={"intermediates": "1"},
            )
            r.raise_for_status()
            data = r.json()
            return _intermediates_to_splits(data.get("intermediates") or [])
    except Exception:
        logger.warning("Échec récupération splits pour l'athlète %s", athlete_ref, exc_info=True)
        return {}


def _fetch_splits_parallel(
    athletes: list[dict],
    max_workers: int = 20,
) -> dict[str, dict[str, str]]:
    """
    Récupère les splits de tous les athlètes en parallèle.
    Clé du dict retourné : bib → splits dict.
    Chaque worker crée son propre httpx.Client pour éviter les conflits de pool.
    """
    ref_key = "id" if athletes and athletes[0].get("id") else "slug"
    tasks: dict[str, str | int] = {
        a["bib"]: a[ref_key]
        for a in athletes
        if a.get(ref_key)
    }
    if not tasks:
        return {}

    results: dict[str, dict[str, str]] = {}

    def fetch(bib: str, ref: str | int) -> tuple[str, dict[str, str]]:
        return bib, _fetch_athlete_splits(ref)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(fetch, bib, ref): bib for bib, ref in tasks.items()}
        for future in as_completed(futures):
            bib, splits = future.result()
            results[bib] = splits

    return results


def _scrape_results_race(slug: str, url: str, client: httpx.Client) -> list[ScrapedResult]:
    """
    Forme 2026 `results.sportinnovation.fr/race/{slug}` (niveau course) :
    GET /api/races/{slug} → meta (title, eventSlug)
    GET /api/events/{eventSlug} → nom et date de l'événement
    GET /api/races/{slug}/results → liste des athlètes
    """
    meta = client.get(f"{API_BASE}/races/{slug}", timeout=15).json()
    if "error" in meta or not meta.get("slug"):
        raise ValueError(f"Course Sportinnovation introuvable : {slug}")
    event_type = _detect_event_type(meta.get("title", ""))
    event_name = ""
    event_date = None
    event_slug = meta.get("eventSlug", "")
    if event_slug:
        ev = client.get(f"{API_BASE}/events/{event_slug}", timeout=15).json()
        event_name = ev.get("title", "")
        raw_date = ev.get("eventDate", "")
        if raw_date:
            try:
                from datetime import date as _date
                event_date = _date.fromisoformat(raw_date[:10])
            except ValueError:
                pass
    athletes = client.get(f"{API_BASE}/races/{slug}/results", timeout=20).json()
    splits_by_bib = _fetch_splits_parallel(athletes)
    return [
        _parse_api_athlete(a, url, event_name, event_type, event_date, splits_by_bib.get(a.get("bib", ""), {}))
        for a in athletes
    ]


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Fetch all participants for a Sportinnovation event."""
    parsed = urlparse(url)

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if "results.sportinnovation.fr" in parsed.netloc:
            kind, ident = _classify_results_url(url)
            if kind == "race":
                # Forme 2026 /race/{slug} : une seule course
                return _scrape_results_race(ident, url, client)

            if kind == "detail":
                # Lien individuel /detail/{id} → résout le raceSlug puis importe toute la course
                result_meta = client.get(f"{API_BASE}/results/{ident}", timeout=15).json()
                race_slug = result_meta.get("raceSlug")
                if not race_slug:
                    raise ValueError(f"Impossible de résoudre le raceSlug depuis le détail : {ident}")
                return _scrape_results_race(race_slug, url, client)

            # Forme /{codeUrl} : niveau événement (toutes ses courses)
            events = client.get(f"{API_BASE}/events", timeout=15).json()
            event = next((e for e in events if e.get("codeUrl") == ident), None)
            if not event:
                raise ValueError(f"Événement {ident} introuvable.")
            event_id = event["id"]
            event_name, event_date = _fetch_event_meta_api(event_id, client)
            races = client.get(f"{API_BASE}/events/{event_id}/races", timeout=15).json()
            results: list[ScrapedResult] = []
            for race in races:
                athletes = client.get(f"{API_BASE}/races/{race['id']}/results", timeout=20).json()
                event_type = _detect_event_type(race.get("title", ""))
                results.extend(
                    _parse_api_athlete(a, url, event_name, event_type, event_date)
                    for a in athletes
                )
            return results

        m = re.search(r"/Resultats/(?:DetailMobile/)?(\d+)", parsed.path)
        if not m:
            raise ValueError(f"URL Sportinnovation non reconnue : {url}")
        event_id = m.group(1)

        # Discover all races in the event group via the <select name=raceSearch>
        first_url = f"https://sportinnovation.fr/Evenements/Resultats/{event_id}"
        resp = client.get(first_url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        race_ids = [
            opt["value"]
            for sel in soup.select("select[name=raceSearch]")
            for opt in sel.find_all("option")
            if opt.get("value", "").isdigit()
        ]
        if not race_ids:
            race_ids = [event_id]

        all_results: list[ScrapedResult] = []
        seen_bibs: set[tuple[str, str]] = set()

        for rid in race_ids:
            race_name, rows, col = _fetch_all_pages(rid, client)
            race_url = f"https://sportinnovation.fr/Evenements/Resultats/{rid}"
            for tds in rows:
                bib_idx = col.get("bib", 1)
                bib_val = tds[bib_idx].strip() if bib_idx < len(tds) else ""
                key = (rid, bib_val)
                if key in seen_bibs:
                    continue
                seen_bibs.add(key)
                all_results.append(_parse_html_row(tds, col, race_url, race_name))

        return all_results
