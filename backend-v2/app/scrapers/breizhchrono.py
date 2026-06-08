"""
Scraper for resultats.breizhchrono.com

Breizh Chrono uses the same underlying platform as Klikego (/v8/evenement/ API,
identical HTML structure). Only the front-end URL format differs:

  Klikego:       https://www.klikego.com/resultats/{slug}/{event-id}
                   ?heat={heat}&search={name}
  Breizh Chrono: https://resultats.breizhchrono.com/resultats-courses/{slug}-{event-id}/{heat}
                   ?search={name}

Note: live.breizhchrono.com URLs are not supported. The frontend detects them
and asks the user to copy the URL from resultats.breizhchrono.com instead.

The detail page HTML (p.text-sm meta line, ranking divs, result-row splits table)
is byte-for-byte identical, so _parse_detail is shared from klikego.
"""
import re
from urllib.parse import parse_qs, urlparse

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult
from .klikego import _parse_detail
from .klikego import _parse_search_row as _klikego_parse_search_row

BASE = "https://resultats.breizhchrono.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://resultats.breizhchrono.com/",
    "Accept": "text/html,*/*",
}


def _parse_bc_date(html: str):
    """Extract event date from BC page HTML. BC embeds an ISO date (YYYY-MM-DD) in the raw HTML."""
    import re as _re
    from datetime import date as _date
    m = _re.search(r'(\d{4}-\d{2}-\d{2})', html)
    if m:
        try:
            return _date.fromisoformat(m.group(1))
        except ValueError:
            pass
    return None


def _parse_bc_url(url: str) -> tuple[str, str, str]:
    """
    Parse a Breizh Chrono results URL into (event_id, heat, slug).

    Supported formats:
      1. /resultats-courses/{slug}-{event-id}/{heat}      (standard)
      2. /bc/resultats/coureur.jsp?ref={event-id}&heat={heat}&dossard={bib}  (direct-bib)
    """
    parsed = urlparse(url)
    path = parsed.path
    params = parse_qs(parsed.query)

    # Format 2: coureur.jsp — event_id in ?ref=, heat in ?heat=
    if "coureur.jsp" in path:
        event_id = params.get("ref", [""])[0].strip()
        heat = params.get("heat", [""])[0].strip()
        return event_id, heat, ""

    # Format 1: /resultats-courses/{slug}-{event-id}/{heat}
    path_parts = [p for p in path.strip("/").split("/") if p]
    slug_with_id = path_parts[1] if len(path_parts) >= 2 else ""
    heat = path_parts[2] if len(path_parts) >= 3 else ""

    m = re.search(r"(\d{10,}-\d+)$", slug_with_id)
    event_id = m.group(1) if m else ""
    slug = slug_with_id[: m.start()].rstrip("-") if m else slug_with_id

    return event_id, heat, slug


def _fetch_all_heats(slug_id: str, client: httpx.Client) -> list[tuple[str, str]]:
    """
    Scrape the event root page and return all (heat_slug, heat_label) pairs.
    heat_label is used to detect relays ("Relais" in the display name).
    """
    try:
        r = client.get(f"{BASE}/resultats-courses/{slug_id}")
        if r.status_code != 200:
            return []
    except Exception:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    prefix = f"/resultats-courses/{slug_id}/"
    heats: list[tuple[str, str]] = []
    seen: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]
        if not href.startswith(prefix):
            continue
        rest = href[len(prefix):]
        if not rest or "/" in rest:  # skip empty or nested paths like /export
            continue
        if rest in seen:
            continue
        seen.add(rest)
        heats.append((rest, link.get_text(strip=True)))

    return heats


def _import_one_heat(
    event_id: str, heat_slug: str, heat_label: str,
    event_name: str, slug: str, event_date, client: httpx.Client,
) -> list[ScrapedResult]:
    """Paginate one heat and return its ScrapedResult list."""
    results: list[ScrapedResult] = []
    is_relay = "relais" in heat_label.lower() or heat_slug.endswith("---")
    source_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat_slug}"
    page = 1
    prev_first_bib: str | None = None

    while True:
        search_url = (
            f"{BASE}/v8/evenement/resultats-search.jsp"
            f"?event={event_id}&heat={heat_slug}&search=&city=&category=&sexe=&page={page}"
        )
        resp = client.get(search_url)
        if resp.status_code != 200:
            break
        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("tr.result-row[data-dossard]")
        if not rows:
            break
        first_bib = rows[0].get("data-dossard", "")
        if first_bib and first_bib == prev_first_bib:
            break
        prev_first_bib = first_bib
        for rank, row in enumerate(rows, start=len(results) + 1):
            r = _klikego_parse_search_row(row, event_id, heat_slug, event_name, slug, rank)
            r.source_url = source_url
            r.provider = "breizhchrono"
            r.is_relay = is_relay
            if event_date:
                r.event_date = event_date
            r.raw_data["heat_slug"] = heat_slug
            results.append(r)
        page += 1

    return results


def scrape_event_all(
    event_id: str, heat: str, event_name: str, slug: str
) -> list[ScrapedResult]:
    """
    Fetch all participants for a Breizh Chrono event.
    If no specific heat is given, auto-discovers all heats from the event root page
    and imports each one with the correct event_type and is_relay per discipline.
    Full splits are fetched only for TCN/Nantais athletes.
    """
    slug_id = f"{slug}-{event_id}"
    results: list[ScrapedResult] = []

    with httpx.Client(follow_redirects=True, timeout=30, headers=HEADERS) as client:
        # Event date — fetch from first available heat page
        event_date = None
        date_page_url = (
            f"{BASE}/resultats-courses/{slug_id}/{heat}" if heat
            else f"{BASE}/resultats-courses/{slug_id}"
        )
        try:
            page_resp = client.get(date_page_url)
            if page_resp.status_code == 200:
                event_date = _parse_bc_date(page_resp.text)
        except Exception:
            pass

        # Discover heats
        if heat:
            # Specific heat requested — import only that one
            heats_to_import = [(heat, "")]
        else:
            heats_to_import = _fetch_all_heats(slug_id, client)
            if not heats_to_import:
                heats_to_import = [(heat, "")]

        for heat_slug, heat_label in heats_to_import:
            heat_results = _import_one_heat(
                event_id, heat_slug, heat_label, event_name, slug, event_date, client
            )
            results.extend(heat_results)

        # Fetch full splits for TCN / Nantais athletes
        _TCN = ("nantais", "tcn", "tri club nant", "triathlon club nant")
        for r in results:
            if r.club and any(k in r.club.lower() for k in _TCN):
                h = r.raw_data.get("heat_slug", heat)
                detail_url = (
                    f"{BASE}/v8/evenement/resultat-participant.jsp"
                    f"?embedded=1&e={event_id}&heat={h}&dossard={r.bib_number}"
                )
                dr = client.get(detail_url)
                if dr.status_code == 200:
                    _parse_detail(dr.text, r, {})

    return results
