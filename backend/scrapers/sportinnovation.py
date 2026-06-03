"""
Scraper for sportinnovation.fr

Two URL formats:

1. www.sportinnovation.fr/Evenements/Resultats/{eventId}  (28/32 URLs)
   - Server-rendered HTML table with full splits
   - GET all rows, filter by name in Python
   - Name cell format: "LASTNAME FirstnameG-CatG" (G=H/F, Cat=category)
   - Columns: Place | Dossard | Nom | Place Cat. | Club | Temps | ... | Tps Nat | T1 | Tps Velo | T2 | Tps CAP

2. results.sportinnovation.fr/detail/{resultId}  (4 URLs)
   - JSON API: GET https://sportinnovation.fr/api/results/{id}
   - No splits available in this format
"""
import re
from datetime import date
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult, MultipleMatchesError
from .utils import normalize_time, normalize_rank

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
    n = race_name.lower()
    if "duathlon" in n:
        for size, code in [("xs", "xs"), ("xxl", "xxl"), ("xl", "xl"), (" l", "l"), (" m", "m"), (" s", "s")]:
            if size in n:
                return f"duathlon-{code}"
        return "duathlon"
    if "swimrun" in n or "swim run" in n or "swim&run" in n:
        return "swimrun"
    if "aquathlon" in n:
        return "aquathlon"
    if "bike" in n and "run" in n:
        return "bike-run"
    if "triathlon" in n or "tri " in n:
        for size, code in [("xs", "xs"), ("xxl", "xxl"), ("xl", "xl"), (" l", "l"), (" m", "m"), (" s", "s")]:
            if size in n:
                return f"triathlon-{code}"
        return "triathlon"
    return "triathlon"


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
    result.total_time = normalize_time(get("total_time"))
    result.swim_time = normalize_time(get("swim_time"))
    result.t1_time = normalize_time(get("t1_time"))
    result.bike_time = normalize_time(get("bike_time"))
    result.t2_time = normalize_time(get("t2_time"))
    result.run_time = normalize_time(get("run_time"))
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


def _search_rows(rows: list[list[str]], search: str, name_col: int) -> list[list[str]]:
    """Client-side filter: rows where the name cell matches all search words."""
    words = search.strip().upper().split()
    if not words:
        return []
    return [
        tds for tds in rows
        if name_col < len(tds) and all(w in tds[name_col].upper() for w in words)
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers — JSON API format (results.sportinnovation.fr)
# ──────────────────────────────────────────────────────────────────────────────

def _scrape_detail_api(result_id: str, client: httpx.Client, url: str) -> ScrapedResult:
    """Fetch a single result from the JSON API (no splits)."""
    r = client.get(f"{API_BASE}/results/{result_id}", timeout=15)
    r.raise_for_status()
    data = r.json()
    if "error" in data:
        raise ValueError(f"Résultat {result_id} introuvable sur Sportinnovation.")

    result = ScrapedResult(source_url=url, provider="sportinnovation")
    result.athlete_name = (data.get("lastName") or "").strip().upper()
    result.athlete_firstname = (data.get("firstName") or "").strip()
    result.bib_number = str(data.get("bib") or "")
    result.club = data.get("clubName") or ""
    result.gender = data.get("sex") or ""
    result.category = data.get("category") or ""
    result.rank_overall = normalize_rank(str(data.get("generalRanking") or ""))
    result.rank_gender = normalize_rank(str(data.get("sexRanking") or ""))
    result.rank_category = normalize_rank(str(data.get("categoryRanking") or ""))
    result.total_time = normalize_time(data.get("officialTime") or data.get("realTime") or "")
    result.raw_data = data
    return result


def _scrape_slug_api(slug: str, search: str, client: httpx.Client, url: str) -> ScrapedResult:
    """Find an athlete in a results.sportinnovation.fr/{slug} event."""
    # Find event by codeUrl
    r = client.get(f"{API_BASE}/events", timeout=15)
    r.raise_for_status()
    events = r.json()
    event = next((e for e in events if e.get("codeUrl") == slug), None)
    if not event:
        raise ValueError(f"Événement « {slug} » introuvable sur Sportinnovation.")

    event_id = event["id"]
    event_name = event.get("title", slug.replace("_", " ").title())
    event_date_raw = event.get("eventDate", "")
    event_date = None
    if event_date_raw:
        try:
            event_date = date.fromisoformat(event_date_raw[:10])
        except ValueError:
            pass

    # Get races
    r2 = client.get(f"{API_BASE}/events/{event_id}/races", timeout=15)
    r2.raise_for_status()
    races = r2.json()
    if not races:
        raise ValueError(f"Aucune épreuve pour {slug}.")

    # Search across all races
    words = search.strip().upper().split()
    all_matches = []
    for race in races:
        race_id = race["id"]
        r3 = client.get(f"{API_BASE}/races/{race_id}/results", timeout=20)
        if r3.status_code != 200:
            continue
        for athlete in r3.json():
            full = f"{athlete.get('lastName','')} {athlete.get('firstName','')}".upper()
            if all(w in full for w in words):
                all_matches.append((athlete, race))

    if not all_matches:
        raise ValueError(f"Athlète « {search} » introuvable sur Sportinnovation ({slug}).")

    if len(all_matches) > 1:
        candidates = [
            {
                "bib": str(a.get("bib", "")),
                "athlete_name": (a.get("lastName") or "").upper(),
                "athlete_firstname": a.get("firstName") or "",
                "total_time": normalize_time(a.get("officialTime") or a.get("realTime") or ""),
                "club": a.get("clubName") or "",
            }
            for a, _ in all_matches
        ]
        raise MultipleMatchesError(candidates)

    athlete, race = all_matches[0]
    result = ScrapedResult(source_url=url, provider="sportinnovation")
    result.event_name = event_name
    result.event_type = _detect_event_type(race.get("title", ""))
    result.event_date = event_date
    result.athlete_name = (athlete.get("lastName") or "").strip().upper()
    result.athlete_firstname = (athlete.get("firstName") or "").strip()
    result.bib_number = str(athlete.get("bib") or "")
    result.club = athlete.get("clubName") or ""
    result.gender = athlete.get("sex") or ""
    result.category = athlete.get("category") or ""
    result.rank_overall = normalize_rank(str(athlete.get("generalRanking") or ""))
    result.rank_gender = normalize_rank(str(athlete.get("sexRanking") or ""))
    result.rank_category = normalize_rank(str(athlete.get("categoryRanking") or ""))
    result.total_time = normalize_time(athlete.get("officialTime") or athlete.get("realTime") or "")
    result.raw_data = athlete
    return result


# ──────────────────────────────────────────────────────────────────────────────
# Public interface
# ──────────────────────────────────────────────────────────────────────────────

def scrape(url: str, bib: str | None = None) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    search = params.get("search", [""])[0].strip()

    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:

        # ── results.sportinnovation.fr/detail/{id} ──
        if "results.sportinnovation.fr" in parsed.netloc:
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            if path_parts and path_parts[0] == "detail" and len(path_parts) >= 2:
                return _scrape_detail_api(path_parts[1], client, url)
            if path_parts and path_parts[0] == "detailAthlete" and len(path_parts) >= 2:
                # detailAthlete/{registration_code} — try extracting result via search
                if not search:
                    raise ValueError(
                        "URL detailAthlete sans nom de recherche. "
                        "Ajoutez ?search=NOM à l'URL ou utilisez /Evenements/Resultats/{id}."
                    )
                # Slug is not available here; can't search without event context
                raise ValueError(
                    "Le format detailAthlete n'est pas supporté. "
                    "Utilisez l'URL de la page résultats : sportinnovation.fr/Evenements/Resultats/{id}."
                )
            # /{slug} event page
            slug = path_parts[0] if path_parts else ""
            if not search and not bib:
                result = ScrapedResult(source_url=url, provider="sportinnovation")
                result.raw_data = {"slug": slug}
                return result
            return _scrape_slug_api(slug, search or bib or "", client, url)

        # ── www.sportinnovation.fr/Evenements/Resultats/{id} ──
        # Support /Evenements/Resultats/{id} and /Evenements/Resultats/DetailMobile/{id}/{x}
        m = re.search(r"/Resultats/(?:DetailMobile/)?(\d+)", parsed.path)
        if not m:
            raise ValueError(f"URL Sportinnovation non reconnue : {url}")
        event_id = m.group(1)

        if not search and not bib:
            result = ScrapedResult(source_url=url, provider="sportinnovation")
            result.raw_data = {"event_id": event_id}
            return result

        # Use server-side POST search when name provided (searches across all races in group)
        # Fall back to client-side filter only when bib is provided
        if search:
            race_name, rows, col = _fetch_html_results(event_id, client, search=search)
            name_col = col.get("name", 2)
            # Server already filtered; apply client-side filter to handle false positives
            matches = _search_rows(rows, search, name_col) if len(rows) > 5 else rows
        else:
            race_name, rows, col = _fetch_html_results(event_id, client)
            name_col = col.get("name", 2)
            bib_col = col.get("bib", 1)
            matches = [tds for tds in rows if bib_col < len(tds) and tds[bib_col] == bib]

        if not matches:
            raise ValueError(
                f"Athlète « {search or bib} » introuvable sur Sportinnovation "
                f"(événement {event_id})."
            )

        if len(matches) > 1:
            candidates = [
                {
                    "bib": tds[col.get("bib", 1)] if col.get("bib", 1) < len(tds) else "",
                    "athlete_name": _parse_name_cell(tds[name_col])[0] if name_col < len(tds) else "",
                    "athlete_firstname": _parse_name_cell(tds[name_col])[1] if name_col < len(tds) else "",
                    "total_time": normalize_time(tds[col.get("total_time", 5)]) if col.get("total_time", 5) < len(tds) else "",
                    "club": tds[col.get("club", 4)] if col.get("club", 4) < len(tds) else "",
                }
                for tds in matches
            ]
            raise MultipleMatchesError(candidates)

        return _parse_html_row(matches[0], col, url, race_name)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """Fetch all participants for a Sportinnovation event."""
    parsed = urlparse(url)

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        if "results.sportinnovation.fr" in parsed.netloc:
            path_parts = [p for p in parsed.path.strip("/").split("/") if p]
            slug = path_parts[0] if path_parts else ""
            r = client.get(f"{API_BASE}/events", timeout=15)
            events = r.json()
            event = next((e for e in events if e.get("codeUrl") == slug), None)
            if not event:
                raise ValueError(f"Événement {slug} introuvable.")
            event_id = event["id"]
            event_name = event.get("title", "")
            event_date_raw = event.get("eventDate", "")
            event_date = None
            if event_date_raw:
                try:
                    event_date = date.fromisoformat(event_date_raw[:10])
                except ValueError:
                    pass
            races = client.get(f"{API_BASE}/events/{event_id}/races", timeout=15).json()
            results = []
            for race in races:
                athletes = client.get(f"{API_BASE}/races/{race['id']}/results", timeout=20).json()
                for a in athletes:
                    res = ScrapedResult(source_url=url, provider="sportinnovation")
                    res.event_name = event_name
                    res.event_type = _detect_event_type(race.get("title", ""))
                    res.event_date = event_date
                    res.athlete_name = (a.get("lastName") or "").strip().upper()
                    res.athlete_firstname = (a.get("firstName") or "").strip()
                    res.bib_number = str(a.get("bib") or "")
                    res.club = a.get("clubName") or ""
                    res.gender = a.get("sex") or ""
                    res.category = a.get("category") or ""
                    res.rank_overall = normalize_rank(str(a.get("generalRanking") or ""))
                    res.total_time = normalize_time(a.get("officialTime") or a.get("realTime") or "")
                    res.raw_data = a
                    results.append(res)
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
