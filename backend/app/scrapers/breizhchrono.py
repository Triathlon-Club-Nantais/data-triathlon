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


def _detect_relay(heat_label: str, heat_slug: str) -> bool:
    """Indique si un heat est une épreuve de relais.

    Le relais est une propriété du heat (et non du participant) : tous les
    résultats d'un même heat héritent donc de cette valeur. Deux signaux :
      - le libellé affiché contient « Relais » (cas nominal) ;
      - à défaut de libellé (heat ciblé directement, sans label), le slug
        d'un heat relais se termine par « --- » sur Breizh Chrono.
    """
    return "relais" in heat_label.lower() or heat_slug.endswith("---")


def _import_one_heat(
    event_id: str, heat_slug: str, heat_label: str,
    event_name: str, slug: str, event_date, client: httpx.Client,
) -> list[ScrapedResult]:
    """Liste complète d'un heat (finishers + DNF/DNS/DSQ) via le moteur partagé."""
    from app.scrapers import klikego_platform as plat
    from app.scrapers.klikego import _detect_event_type

    is_relay = _detect_relay(heat_label, heat_slug)
    source_url = f"{BASE}/resultats-courses/{slug}-{event_id}/{heat_slug}"
    heat_page = client.get(source_url)
    heat_page_html = heat_page.text if heat_page.status_code == 200 else ""

    results = plat.build_heat_results(
        base=BASE,
        provider="breizhchrono",
        event_id=event_id,
        heat=heat_slug,
        heat_page_html=heat_page_html,
        event_name=event_name,
        slug=slug,
        event_type=_detect_event_type(heat_slug, slug),
        source_url=source_url,
        event_date=event_date,
        client=client,
    )
    # is_relay est une propriété du heat : on la propage à tous ses résultats.
    for r in results:
        r.is_relay = is_relay
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

        # Splits fins pour les athlètes TCN/Nantais (priment sur les splits inter)
        from app.scrapers.klikego import _TCN_KEYWORDS, _parse_detail
        for r in results:
            if r.club and any(k in r.club.lower() for k in _TCN_KEYWORDS):
                h = r.raw_data.get("heat_slug", heat)
                dr = client.get(
                    f"{BASE}/v8/evenement/resultat-participant.jsp"
                    f"?embedded=1&e={event_id}&heat={h}&dossard={r.bib_number}"
                )
                if dr.status_code == 200:
                    # Les splits fins TCN repeuplent les slots, qui priment sur les splits inter pré-remplis.
                    r.swim_time = r.t1_time = r.bike_time = r.t2_time = r.run_time = ""
                    _parse_detail(dr.text, r, {})

    return results
