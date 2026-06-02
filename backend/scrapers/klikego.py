"""
Scraper for klikego.com results.
URL example:
  https://www.klikego.com/resultats/triathlon-dangers-entre-loire-et-maine-2026/1700025627600-3
    ?heat=triathlon-m-individuel&search=CADEAU&city=&category=&sexe=

Klikego API returns HTML (not JSON):
  Search: GET /v8/evenement/resultats-search.jsp?event={id}&heat={heat}&search={name}
  Detail: GET /v8/evenement/resultat-participant.jsp?embedded=1&e={id}&heat={heat}&dossard={bib}
"""
import re
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult
from .utils import normalize_time, normalize_rank

BASE = "https://www.klikego.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Referer": "https://www.klikego.com/",
    "Accept": "text/html,*/*",
}


def _detect_heat(event_id: str, client: httpx.Client) -> str:
    """Fetch the event results page and extract the first heat= value found."""
    try:
        r = client.get(f"{BASE}/resultats/{event_id}")
        heats = re.findall(r'heat=([^&<>\s"\']+)', r.text)
        return heats[0] if heats else ""
    except httpx.HTTPError:
        return ""


def scrape(url: str) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    path_parts = [p for p in parsed.path.strip("/").split("/") if p]

    event_id = path_parts[-1] if path_parts else ""
    heat = params.get("heat", [""])[0]
    search = params.get("search", [""])[0].strip()

    result = ScrapedResult(source_url=url, provider="klikego")

    # Event name from URL slug
    slug = path_parts[-2] if len(path_parts) >= 2 else ""
    if slug:
        result.event_name = slug.replace("-", " ").title()

    result.event_type = _detect_event_type(heat, slug)
    raw: dict = {"event_id": event_id, "heat": heat, "search": search}

    if not search:
        result.raw_data = raw
        return result  # need a name to search

    with httpx.Client(follow_redirects=True, timeout=20, headers=HEADERS) as client:
        # Auto-detect heat when missing from URL
        if not heat:
            heat = _detect_heat(event_id, client)
            raw["heat"] = heat
            result.event_type = _detect_event_type(heat, slug)
        # 1 — Search by name
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

        # Find result row — desktop rows have data-dossard
        row = soup.select_one("tr.result-row[data-dossard]")
        if row is None:
            raise ValueError(
                f"Athlète « {search} » introuvable sur Klikego (événement {event_id}). "
                "Vérifiez l'orthographe du nom."
            )

        dossard = row.get("data-dossard", "")
        result.bib_number = dossard

        # Parse basic info from search result row
        cells = row.find_all("td")
        if cells:
            # Name cell contains "NOM Prénom"
            name_cell = row.select_one("td.truncate")
            if name_cell:
                full = name_cell.get_text(strip=True)
                parts = full.split()
                # Convention: UPPERCASE tokens = surname
                i = 0
                while i < len(parts) and parts[i].isupper():
                    i += 1
                result.athlete_name = " ".join(parts[:i])
                result.athlete_firstname = " ".join(parts[i:])

            # Time (font-mono cell)
            time_cell = row.select_one("td.font-mono")
            if time_cell:
                result.total_time = normalize_time(time_cell.get_text(strip=True))

        # 2 — Fetch participant detail for splits + full rankings
        detail_url = (
            f"{BASE}/v8/evenement/resultat-participant.jsp"
            f"?embedded=1&e={event_id}&heat={heat}&dossard={dossard}"
        )
        detail_resp = client.get(detail_url)
        if detail_resp.status_code == 200:
            _parse_detail(detail_resp.text, result, raw)

    result.raw_data = raw
    return result


def _parse_detail(html: str, result: ScrapedResult, raw: dict):
    soup = BeautifulSoup(html, "lxml")
    raw["detail_html"] = html[:500]

    # Name + metadata line: "M - Dossard N°2141 - V1 - LE MANS TRIATHLON"
    meta_p = soup.select_one("p.text-sm")
    if meta_p:
        meta = meta_p.get_text(strip=True)
        raw["meta"] = meta
        parts = [p.strip() for p in meta.split("-")]
        for p in parts:
            p_low = p.lower()
            # Collapse internal spaces for gender/category matching ("BE F" → "BEF")
            p_compact = re.sub(r"\s+", "", p)
            if p_compact.upper() in ("M", "F", "H"):
                # "H" is an alias for "M" used by some timing systems
                result.gender = "M" if p_compact.upper() == "H" else p_compact.upper()
            elif "dossard" in p_low:
                result.bib_number = re.sub(r"[^\d]", "", p)
            elif re.match(
                r"^(SE[HF]?|SEN[HF]?|S[1-9]\d*[HF]?|MA[1-9]\d*[HF]?|M[1-9]\d*[HF]?|"
                r"V[1-5][HF]?|VET[HF]?\d*|JU[HF]?|ES[HF]?|ESP[HF]?|CA[HF]?|BE[HF]?|"
                r"MI[HF]?|PO[HF]?|PU[HF]?)$",
                p_compact, re.I
            ):
                result.category = p_compact
            elif not any(x in p_low for x in ("dossard", "n°")) and p_compact.upper() not in ("M", "F", "H"):
                if result.club == "":
                    result.club = p

    # Official time + Rankings — find label divs by exact text, then read sibling
    rank_map = {
        "classement général": "overall",
        "classement catégorie": "category",
        "classement sexe": "gender",
        "classement genre": "gender",
    }
    for div in soup.find_all("div"):
        text = div.get_text(strip=True)
        text_low = text.lower()

        if text == "Temps Officiel":
            val_div = div.find_next_sibling("div")
            if val_div:
                t = normalize_time(val_div.get_text(strip=True))
                if t:
                    result.total_time = t

        for label, field in rank_map.items():
            if text_low == label:
                val_div = div.find_next_sibling("div")
                if val_div:
                    rank_text = val_div.get_text(strip=True)
                    m = re.match(r"(\d+)", rank_text)
                    if m:
                        rank = int(m.group(1))
                        if field == "overall":
                            result.rank_overall = rank
                        elif field == "category":
                            result.rank_category = rank
                        else:
                            result.rank_gender = rank

    # Split times — table rows: [stage_name, time, pos_gen, pos_cat]
    # Order: most specific (longest) patterns first to avoid "natation" matching
    # "transition natation - vélo" before the transition key does.
    split_map = [
        # Transitions — specific before generic
        ("transition natation", "t1"),
        ("transition nat", "t1"),
        ("chg nat", "t1"),          # "Chg Nat." (changement natation)
        ("transition vélo", "t2"),
        ("transition velo", "t2"),
        ("chg vé", "t2"),           # "Chg Vélo"
        ("chg ve", "t2"),           # "Chg Velo" (ASCII fallback)
        ("t1", "t1"),
        ("t2", "t2"),
        # Swim
        ("natation", "swim"),
        ("swim", "swim"),
        # Bike
        ("vélo", "bike"),
        ("velo", "bike"),
        ("bike", "bike"),
        ("cyclisme", "bike"),
        # Run — duathlon: "CAP 1" / "Course à pied 1" (run1) → swim slot, "CAP 2" / "Course à pied 2" → run slot
        ("course à pied 1", "swim"),
        ("course a pied 1", "swim"),
        ("course à pied 2", "run"),
        ("course a pied 2", "run"),
        ("cap 1", "swim"),
        ("cap 2", "run"),
        ("course", "run"),
        ("cap", "run"),
        ("run", "run"),
        ("à pied", "run"),
        ("a pied", "run"),
    ]

    # --- Collect split rows ---
    splits_raw: list[tuple[str, str, str | None]] = []  # (stage, time_norm, field|None)
    for row in soup.select("tr.result-row[data-dossard]"):
        tds = row.find_all("td")
        if len(tds) < 2:
            continue
        stage = tds[0].get_text(strip=True).lower()
        time_norm = normalize_time(tds[1].get_text(strip=True))

        # "temps réel" row = total time reported by timing system, not a split
        if "temps" in stage and "réel" in stage:
            if not result.total_time:
                result.total_time = time_norm
            continue

        field: str | None = None
        for key, f in split_map:
            if key in stage:
                field = f
                break
        splits_raw.append((stage, time_norm, field))

    # --- Detect cumulative times ---
    # If times for mapped stages are strictly increasing → they are cumulative
    # (checkpoints like KM42 are skipped for this check)
    def _secs(t: str) -> int:
        if not t:
            return 0
        p = t.split(":")
        try:
            return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
        except (IndexError, ValueError):
            return 0

    mapped_secs = [_secs(t) for _, t, f in splits_raw if f and t]
    is_cumulative = (
        len(mapped_secs) >= 2
        and all(mapped_secs[i] < mapped_secs[i + 1] for i in range(len(mapped_secs) - 1))
    )
    raw["cumulative"] = is_cumulative

    # --- Assign split times (computing deltas if cumulative) ---
    prev_secs = 0
    last_mapped_secs = 0
    for stage, time_norm, field in splits_raw:
        secs = _secs(time_norm)

        if is_cumulative and secs > 0:
            if field is not None:
                # Duration = cumulative_now - cumulative_after_previous_mapped_stage
                dur = secs - prev_secs
                prev_secs = secs
                last_mapped_secs = secs
                h, rem = divmod(dur, 3600)
                m, s = divmod(rem, 60)
                time_val = f"{h:02d}:{m:02d}:{s:02d}"
            else:
                # Intermediate checkpoint (e.g. KM42) — store as-is, don't shift prev
                time_val = time_norm
        else:
            time_val = time_norm

        if field == "swim":
            result.swim_time = time_val
        elif field == "t1":
            result.t1_time = time_val
        elif field == "bike":
            result.bike_time = time_val
        elif field == "t2":
            result.t2_time = time_val
        elif field == "run":
            result.run_time = time_val
        else:
            raw[f"split_{stage}"] = time_val

    # If cumulative and run is absent, derive from total − last mapped stage end
    if is_cumulative and not result.run_time and result.total_time:
        total_s = _secs(result.total_time)
        if total_s > last_mapped_secs > 0:
            run_s = total_s - last_mapped_secs
            h, rem = divmod(run_s, 3600)
            m, s = divmod(rem, 60)
            result.run_time = f"{h:02d}:{m:02d}:{s:02d}"


def _detect_event_type(heat: str, slug: str = "") -> str:
    # Check sport type first (slug covers swimrun events whose heat is "Format L…")
    combined = (heat + " " + slug).lower()
    h = heat.lower()

    if "swimrun" in combined or "swim-run" in combined:
        # Format L/M/S from heat "format-l-…", "format-m-…", "format-s-…"
        if "format-l" in h:
            return "swimrun-l"
        if "format-m" in h:
            return "swimrun-m"
        if "format-s" in h:
            return "swimrun-s"
        return "swimrun"

    if "duathlon" in combined:
        # Strip "duathlon-" prefix to read the format indicator
        suffix = h.replace("duathlon-", "").replace("duathlon", "")
        if "xs" in suffix or "extra-short" in suffix:
            return "duathlon-xs"
        if suffix.startswith("s-") or "-s-" in suffix or "sprint" in suffix:
            return "duathlon-s"
        if suffix.startswith("m-") or "-m-" in suffix:
            return "duathlon-m"
        if suffix.startswith("l-") or "-l-" in suffix:
            return "duathlon-l"
        return "duathlon"

    # Other multisport — must be checked BEFORE triathlon distance patterns to
    # prevent e.g. "aquathlon-s-champnat" matching the "-s" triathlon-s rule.
    if "aquathlon" in combined:
        return "aquathlon"
    if "aquarun" in combined:
        return "aquarun"
    if any(p in combined for p in ("bike & run", "bike and run", "bike run", "bikerun",
                                    "run & bike", "run and bike", "bike-run")):
        return "bike-run"

    # Triathlon distance from heat name
    if "xxl" in h or "ironman" in h:
        return "triathlon-xl"
    if "-l" in h or "longue" in h:
        return "triathlon-l"
    if "-m" in h or "olymp" in h:
        return "triathlon-m"
    if "-s" in h or "sprint" in h:
        return "triathlon-s"
    return h or "triathlon"
