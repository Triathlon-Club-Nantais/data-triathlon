"""
Scraper for timepulse.fr results — pure XML parsing, no Playwright.

TimePulse exposes a data API that returns a wiclax-format XML:
  https://www.timepulse.fr/resultats/api/data.php?id_event={id}

The XML contains:
  <Epreuve>        event metadata
  <S id="N" nom="Natation|T1|Vélo|T2|Course à pied" />   series definitions
  <E d="{bib}" n="{NOM Prénom}" c="{club}" x="{M|F}" ca="{category}" p="{parcours}" />
  <R d="{bib}" t="{total}" s0="{split0}" … s4="{split4}" />

When a search name matches multiple athletes a ValueError is raised listing
all matches so the user can refine their query.
"""
import re
from datetime import date as date_t
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import httpx

from .base import ScrapedResult
from .utils import normalize_time, split_athlete_name

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

_DATA_API_URLS = [
    "https://www.timepulse.fr/resultats/api/data.php?id_event={id_event}",
    "https://www.timepulse.fr/epreuves/resultats/api/data.php?id_event={id_event}",
]


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _fetch_xml(id_event: str) -> str:
    for tpl in _DATA_API_URLS:
        try:
            r = httpx.get(
                tpl.format(id_event=id_event),
                follow_redirects=True, timeout=20, headers=_HEADERS,
            )
            if r.status_code == 200 and "<Epreuve" in r.text:
                return r.text
        except httpx.HTTPError:
            continue
    return ""


def _attrs(tag: str) -> dict[str, str]:
    """Extract all key="value" attributes from an XML tag string."""
    return dict(re.findall(r'(\w+)="([^"]*)"', tag))


def _find_tag(xml: str, tag: str, attr: str, value: str) -> str | None:
    """Return the first <tag …attr="value"…/> or None."""
    m = re.search(
        r"<" + tag + r"\s[^>]*\b" + attr + r'="' + re.escape(value) + r'"[^>]*/?>',
        xml,
    )
    return m.group() if m else None


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _normalize_name(s: str) -> str:
    """Collapse all whitespace variants to a single space for comparison."""
    return re.sub(r"[\s\xa0]+", " ", s).strip().upper()


def _search_athletes(xml: str, name: str) -> list[tuple[str, str, str]]:
    """
    Return [(bib, full_name, category), …] for athletes whose name
    contains the search string (case-insensitive, whitespace-normalised).
    """
    name_norm = _normalize_name(name)
    matches = []
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        a = _attrs(m.group())
        full_name = a.get("n", "")
        if name_norm in _normalize_name(full_name):
            matches.append((a.get("d", ""), full_name, a.get("ca", "")))
    return matches


# ---------------------------------------------------------------------------
# Series → split field mapping
# ---------------------------------------------------------------------------

_SERIES_SPLIT_MAP = [
    ("natation", "swim"), ("swim", "swim"),
    ("t1", "t1"), ("transition 1", "t1"), ("chg nat", "t1"),
    ("vélo", "bike"), ("velo", "bike"), ("bike", "bike"), ("cyclisme", "bike"),
    ("t2", "t2"), ("transition 2", "t2"), ("chg v", "t2"),
    ("course", "run"), ("cap", "run"), ("run", "run"), ("à pied", "run"),
]


def _series_field(nom: str) -> str | None:
    n = nom.lower().strip()
    for key, field in _SERIES_SPLIT_MAP:
        if key in n:
            return field
    return None


def _parse_series(xml: str) -> dict[str, str]:
    """Return {s-index: field} e.g. {"s0": "swim", "s1": "t1", ...}

    Special case — duathlon: both stages are "Course à pied" (no swim).
    The first run is mapped to the "swim" slot so both runs have distinct slots.
    """
    entries: list[tuple[str, str]] = []
    for m in re.finditer(r"<S\s[^>]+/>", xml):
        a = _attrs(m.group())
        idx = a.get("id", "")
        nom = a.get("nom", a.get("lb", ""))
        field = _series_field(nom)
        if idx and field:
            entries.append((idx, field))

    run_count  = sum(1 for _, f in entries if f == "run")
    swim_count = sum(1 for _, f in entries if f == "swim")
    is_duathlon_layout = (run_count == 2 and swim_count == 0)

    mapping: dict[str, str] = {}
    first_run_seen = False
    for idx, field in entries:
        if field == "run" and is_duathlon_layout:
            if not first_run_seen:
                mapping[f"s{idx}"] = "swim"   # run1 → swim slot (no swimming in duathlon)
                first_run_seen = True
            else:
                mapping[f"s{idx}"] = "run"
        else:
            mapping[f"s{idx}"] = field
    return mapping


# ---------------------------------------------------------------------------
# Rankings computation
# ---------------------------------------------------------------------------

def _secs(t: str) -> int:
    if not t:
        return 0
    p = t.split(":")
    try:
        return int(p[0]) * 3600 + int(p[1]) * 60 + int(p[2])
    except (IndexError, ValueError):
        return 0


def _compute_ranks(
    xml: str, bib: str, parcours: str, gender: str, category: str
) -> tuple[int | None, int | None, int | None]:
    """
    Compute (rank_overall, rank_gender, rank_category) within the athlete's
    parcours by sorting all R entries by total time.
    """
    # Gather bibs for the same parcours
    parcours_bibs: set[str] = set()
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        a = _attrs(m.group())
        if a.get("p", "") == parcours:
            parcours_bibs.add(a.get("d", ""))

    # Gather E attrs indexed by bib for gender/category filtering
    e_by_bib: dict[str, dict] = {}
    for m in re.finditer(r"<E\s[^>]+/>", xml):
        a = _attrs(m.group())
        e_by_bib[a.get("d", "")] = a

    # Gather R entries for same parcours, keyed by bib with time in seconds
    results: list[tuple[int, str]] = []  # (secs, bib)
    for m in re.finditer(r"<R\s[^>]+/>", xml):
        a = _attrs(m.group())
        b = a.get("d", "")
        if b in parcours_bibs:
            t = normalize_time(a.get("t", ""))
            s = _secs(t)
            if s:
                results.append((s, b))

    results.sort(key=lambda x: x[0])

    rank_overall = rank_gender = rank_category = None

    overall_pos = gender_pos = category_pos = 0
    for s, b in results:
        e = e_by_bib.get(b, {})
        overall_pos += 1
        if e.get("x", "") == gender:
            gender_pos += 1
        # Category rank: count same-gender + same-category (categories are gender-specific
        # in French triathlon, e.g. V1H vs V1F; counting across genders would inflate the rank)
        if e.get("ca", "") == category and e.get("x", "") == gender:
            category_pos += 1

        if b == bib:
            rank_overall = overall_pos
            rank_gender = gender_pos
            rank_category = category_pos
            break

    return rank_overall, rank_gender, rank_category


def _parse_event_date(date_str: str) -> date_t | None:
    """Parse TimePulse XML date string (YYYY-MM-DD or DD/MM/YYYY) into a date object."""
    # ISO format YYYY-MM-DD
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str)
    if m:
        try:
            return date_t(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # French format DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{2})/(\d{4})", date_str)
    if m:
        try:
            return date_t(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return None


# ---------------------------------------------------------------------------
# Main scrape function
# ---------------------------------------------------------------------------

def scrape(url: str) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    bib = params.get("bib", [""])[0]
    id_event = params.get("id_event", [""])[0]
    search = params.get("search", [""])[0].strip()

    # Fallback: extract id_event from the URL path when absent from query params.
    # Handles https://www.timepulse.fr/epreuves/resultats/3090
    #      and https://www.timepulse.fr/resultats/3090
    if not id_event:
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        for part in reversed(path_parts):
            if re.match(r"^\d+$", part):
                id_event = part
                break

    if not id_event:
        raise ValueError("Paramètre id_event manquant dans l'URL TimePulse.")

    xml = _fetch_xml(id_event)
    if not xml:
        raise ValueError(f"Impossible de récupérer les données de l'événement {id_event}.")

    # Resolve name → bib
    if not bib and search:
        matches = _search_athletes(xml, search)
        if not matches:
            raise ValueError(
                f"Athlète « {search} » introuvable sur l'événement TimePulse {id_event}. "
                "Vérifiez l'orthographe du nom."
            )
        if len(matches) > 1:
            listing = ", ".join(f"{name} (dossard {b})" for b, name, _ in matches)
            raise ValueError(
                f"Plusieurs athlètes correspondent à « {search} » : {listing}. "
                "Précisez le prénom ou le dossard."
            )
        bib = matches[0][0]
        new_qs = {k: v[0] for k, v in params.items()}
        new_qs["bib"] = bib
        new_qs.pop("search", None)
        url = urlunparse(parsed._replace(query=urlencode(new_qs)))

    if not bib:
        raise ValueError(
            "Numéro de dossard manquant. Ajoutez &bib=NUMERO à l'URL "
            "ou saisissez le nom de l'athlète."
        )

    result = ScrapedResult(source_url=url, provider="timepulse", bib_number=bib)
    raw: dict = {"bib": bib, "search": search, "id_event": id_event}

    # --- Event metadata ---
    epreuve_m = re.search(r"<Epreuve\s[^>]+>", xml)
    if epreuve_m:
        ea = _attrs(epreuve_m.group())
        result.event_name = ea.get("nom", "")
        date_str = ea.get("dates", "")
        raw["event_dates"] = date_str
        if date_str:
            result.event_date = _parse_event_date(date_str)

    result.event_type = _detect_event_type(result.event_name)

    # --- Series → split field mapping ---
    series_map = _parse_series(xml)  # {"s0": "swim", "s1": "t1", …}
    raw["series_map"] = series_map

    # --- Athlete registration (E tag) ---
    e_tag = _find_tag(xml, "E", "d", bib)
    parcours = ""
    if e_tag:
        ea = _attrs(e_tag)
        full_name = ea.get("n", "")
        surname, firstname = split_athlete_name(full_name)
        result.athlete_name = surname
        result.athlete_firstname = firstname
        result.club = ea.get("c", "")
        result.gender = ea.get("x", "")
        result.category = ea.get("ca", "")
        parcours = ea.get("p", "")

    # --- Result (R tag) ---
    r_tag = _find_tag(xml, "R", "d", bib)
    if r_tag:
        ra = _attrs(r_tag)
        result.total_time = normalize_time(ra.get("t", ""))
        # Map s0…sN to swim/t1/bike/t2/run via series_map.
        # "First set wins": if a field is already populated (e.g. swimrun with
        # multiple natation stages), subsequent values go to raw_data.
        for key, field in series_map.items():
            t = normalize_time(ra.get(key, ""))
            if not t:
                continue
            if field == "swim":
                if not result.swim_time:
                    result.swim_time = t
                else:
                    raw[f"split_{key}"] = t
            elif field == "t1":
                if not result.t1_time:
                    result.t1_time = t
                else:
                    raw[f"split_{key}"] = t
            elif field == "bike":
                if not result.bike_time:
                    result.bike_time = t
                else:
                    raw[f"split_{key}"] = t
            elif field == "t2":
                if not result.t2_time:
                    result.t2_time = t
                else:
                    raw[f"split_{key}"] = t
            elif field == "run":
                if not result.run_time:
                    result.run_time = t
                else:
                    raw[f"split_{key}"] = t
        raw["r_tag"] = r_tag

        # Derive run_time when missing but total and other splits are known.
        # Handles events with non-standard segment naming (e.g. "Boucle 1-5")
        # where the run leg cannot be mapped from series labels.
        if result.total_time and not result.run_time:
            total_s = _secs(result.total_time)
            known_s = sum(
                _secs(t)
                for t in [result.swim_time, result.t1_time, result.bike_time, result.t2_time]
                if t
            )
            if total_s > 0 and known_s > 0 and total_s > known_s:
                run_s = total_s - known_s
                h_, rem = divmod(run_s, 3600)
                m_, s_ = divmod(rem, 60)
                result.run_time = f"{h_:02d}:{m_:02d}:{s_:02d}"
                raw["run_derived"] = True
    else:
        raw["warning"] = "Pas de résultat disponible pour ce dossard."

    # --- Rankings ---
    if parcours and result.gender and result.category:
        ro, rg, rc = _compute_ranks(xml, bib, parcours, result.gender, result.category)
        result.rank_overall = ro
        result.rank_gender = rg
        result.rank_category = rc

    result.raw_data = raw
    return result


# ---------------------------------------------------------------------------
# Event type detection
# ---------------------------------------------------------------------------

def _detect_event_type(name: str) -> str:
    n = name.lower()
    # Check specific sports FIRST to avoid false triathlon-size matches.
    # e.g. "Duathlon Sprint" must not become "triathlon-s" via the sprint check.
    if "aquathlon" in n:
        return "aquathlon"
    if "aquarun" in n:
        return "aquarun"
    if any(p in n for p in ("bike & run", "bike and run", "bike run", "bikerun",
                             "run & bike", "run and bike")):
        return "bike-run"
    if "swimrun" in n or "swim run" in n or "swim-run" in n:
        return "swimrun"
    if "duathlon" in n:
        if "sprint" in n:
            return "duathlon-s"
        if " m " in n or "olympique" in n:
            return "duathlon-m"
        if " l " in n or "longue" in n:
            return "duathlon-l"
        return "duathlon"
    # Triathlon distances
    if "xxl" in n or "ironman" in n or "longue distance" in n:
        return "triathlon-xl"
    if "half" in n or "70.3" in n or " l " in n or "longue" in n:
        return "triathlon-l"
    if "olympique" in n or "olympic" in n or "triathlon-m" in n:
        return "triathlon-m"
    if "sprint" in n or "triathlon-s" in n:
        return "triathlon-s"
    return "triathlon"
