"""
Scraper for resultats.breizhchrono.com

Breizh Chrono uses the same underlying platform as Klikego (/v8/evenement/ API,
identical HTML structure). Only the front-end URL format differs:

  Klikego:       https://www.klikego.com/resultats/{slug}/{event-id}
                   ?heat={heat}&search={name}
  Breizh Chrono: https://resultats.breizhchrono.com/resultats-courses/{slug}-{event-id}/{heat}
                   ?search={name}

The detail page HTML (p.text-sm meta line, ranking divs, result-row splits table)
is byte-for-byte identical, so _parse_detail is shared from klikego.
"""
import re
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult, MultipleMatchesError
from .utils import normalize_time, parse_fr_date
from .klikego import _parse_detail, _parse_search_row as _klikego_parse_search_row, _detect_event_type as _klikego_detect_event_type

BASE = "https://resultats.breizhchrono.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://resultats.breizhchrono.com/",
    "Accept": "text/html,*/*",
}


def _parse_bc_url(url: str) -> tuple[str, str, str]:
    """
    Parse a Breizh Chrono results URL into (event_id, heat, slug).

    URL format:
      /resultats-courses/{slug}-{event-id}/{heat}

    event-id: 10+ digits, hyphen, 1+ digits  e.g. 1700025627600-3
    heat:     last path segment               e.g. triathlon-s-individuel
    slug:     human-readable prefix           e.g. triathlon-dangers-entre-loire-et-maine-2026
    """
    path_parts = [p for p in urlparse(url).path.strip("/").split("/") if p]
    # path_parts[0] = "resultats-courses"
    # path_parts[1] = "{slug}-{event-id}"
    # path_parts[2] = "{heat}"
    slug_with_id = path_parts[1] if len(path_parts) >= 2 else ""
    heat = path_parts[2] if len(path_parts) >= 3 else ""

    m = re.search(r"(\d{10,}-\d+)$", slug_with_id)
    event_id = m.group(1) if m else ""
    slug = slug_with_id[: m.start()].rstrip("-") if m else slug_with_id

    return event_id, heat, slug


def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str
) -> list[ScrapedResult]:
    """
    Fetch all participants for a Breizh Chrono event by paginating the search
    endpoint with an empty search term. Shares the same /v8/ API as Klikego.
    Full splits are fetched only for club athletes ('nantais').
    """
    results: list[ScrapedResult] = []

    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        # Fetch event date
        event_date = None
        try:
            page_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat}" if slug and heat else ""
            if page_url:
                page_resp = client.get(page_url)
                if page_resp.status_code == 200:
                    date_el = BeautifulSoup(page_resp.text, "lxml").select_one("span.tag.tag-brand.tag-ghost")
                    if date_el:
                        event_date = parse_fr_date(date_el.get_text(strip=True))
        except Exception:
            pass

        page = 1
        rank = 1
        while True:
            search_url = (
                f"{BASE}/v8/evenement/resultats-search.jsp"
                f"?event={event_id}&heat={heat}&search=&city=&category=&sexe=&page={page}"
            )
            resp = client.get(search_url)
            if resp.status_code != 200:
                break
            soup = BeautifulSoup(resp.text, "lxml")
            rows = soup.select("tr.result-row[data-dossard]")
            if not rows:
                break
            for row in rows:
                r = _klikego_parse_search_row(row, event_id, heat, event_name, slug, rank)
                r.source_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat}"
                r.provider = "breizhchrono"
                if event_date:
                    r.event_date = event_date
                results.append(r)
                rank += 1
            page += 1

        for r in results:
            if r.club and "nantais" in r.club.lower():
                detail_url = (
                    f"{BASE}/v8/evenement/resultat-participant.jsp"
                    f"?embedded=1&e={event_id}&heat={heat}&dossard={r.bib_number}"
                )
                dr = client.get(detail_url)
                if dr.status_code == 200:
                    _parse_detail(dr.text, r, {})

    return results


def scrape(url: str, bib: str | None = None) -> ScrapedResult:
    parsed_url = urlparse(url)
    params = parse_qs(parsed_url.query)
    search = params.get("search", [""])[0].strip()

    event_id, heat, slug = _parse_bc_url(url)

    result = ScrapedResult(source_url=url, provider="breizhchrono")

    if slug:
        result.event_name = slug.replace("-", " ").title()

    result.event_type = _klikego_detect_event_type(heat, slug)
    raw: dict = {"event_id": event_id, "heat": heat, "search": search}

    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        # Fetch event date from the event page
        try:
            page_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat}" if slug and heat else url
            page_resp = client.get(page_url)
            if page_resp.status_code == 200:
                from bs4 import BeautifulSoup as _BS
                _soup = _BS(page_resp.text, "lxml")
                date_el = _soup.select_one("span.tag.tag-brand.tag-ghost")
                if date_el:
                    result.event_date = parse_fr_date(date_el.get_text(strip=True))
        except Exception:
            pass

        if bib:
            dossard = bib
            result.bib_number = dossard
        else:
            if not search:
                result.raw_data = raw
                return result

            search_url = (
                f"{BASE}/v8/evenement/resultats-search.jsp"
                f"?event={event_id}&heat={heat}&search={search}&city=&category=&sexe=&page="
            )
            resp = client.get(search_url)
            if resp.status_code != 200:
                raw["search_error"] = resp.status_code
                result.raw_data = raw
                return result

            soup = BeautifulSoup(resp.text, "lxml")
            raw["search_html"] = resp.text[:500]

            rows = soup.select("tr.result-row[data-dossard]")
            if not rows:
                raise ValueError(
                    f"Athlète « {search} » introuvable sur Breizh Chrono (événement {event_id}). "
                    "Vérifiez l'orthographe du nom."
                )

            if len(rows) > 1:
                candidates = []
                for r in rows:
                    name_cell = r.select_one("td.truncate")
                    full = name_cell.get_text(strip=True) if name_cell else ""
                    parts = full.split()
                    i = 0
                    while i < len(parts) and parts[i].isupper():
                        i += 1
                    time_cell = r.select_one("td.font-mono")
                    truncate_cells = r.select("td.truncate")
                    candidates.append({
                        "bib": r.get("data-dossard", ""),
                        "athlete_name": " ".join(parts[:i]),
                        "athlete_firstname": " ".join(parts[i:]),
                        "total_time": normalize_time(time_cell.get_text(strip=True)) if time_cell else "",
                        "club": truncate_cells[1].get_text(strip=True) if len(truncate_cells) >= 2 else "",
                    })
                raise MultipleMatchesError(candidates)

            row = rows[0]
            dossard = row.get("data-dossard", "")
            result.bib_number = dossard

            name_cell = row.select_one("td.truncate")
            if name_cell:
                full = name_cell.get_text(strip=True)
                parts = full.split()
                i = 0
                while i < len(parts) and parts[i].isupper():
                    i += 1
                result.athlete_name = " ".join(parts[:i])
                result.athlete_firstname = " ".join(parts[i:])

            time_cell = row.select_one("td.font-mono")
            if time_cell:
                result.total_time = normalize_time(time_cell.get_text(strip=True))

        detail_url = (
            f"{BASE}/v8/evenement/resultat-participant.jsp"
            f"?embedded=1&e={event_id}&heat={heat}&dossard={dossard}"
        )
        detail_resp = client.get(detail_url)
        if detail_resp.status_code == 200:
            _parse_detail(detail_resp.text, result, raw)

    result.raw_data = raw
    return result
