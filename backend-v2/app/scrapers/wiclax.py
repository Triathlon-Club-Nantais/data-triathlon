"""
Scraper for wiclax G-Live results (chronosmetron.wiclax-results.com, etc.)
URL example:
  https://chronosmetron.wiclax-results.com/G-Live/g-live.html
    ?f=../Triathlon%20de%20la%20Roche%202026/Triathlon%20de%20la%20Roche.clax&B=6159

The .clax file is an XML file containing all results.
We fetch it and find the competitor by bib number (B param).
"""
import re
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlparse, urlunparse

import httpx

from .base import MultipleMatchesError, ScrapedResult
from .utils import normalize_rank, normalize_time, split_athlete_name

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}



def _parse_competitor(comp, url: str, event_name: str, event_type: str) -> ScrapedResult:
    """Build a ScrapedResult from a single competitor XML element.
    Handles both Wiclax Competitor/Runner format and TimePulse-style E format.
    """
    bib = _get_competitor_bib(comp)
    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=bib)
    result.event_name = event_name

    # p= (parcours) gives per-competitor discipline in ChronoSmetron format
    # e.g. "Triathlon M", "Triathlon L", "Relais S" — takes priority over root event name
    p_attr = comp.get("p") or comp.get("P") or ""
    if p_attr:
        event_type = _detect_event_type(p_attr)
        result.is_relay = "relais" in p_attr.lower() or "relay" in p_attr.lower()

    result.event_type = event_type

    # Try standard Competitor/Runner attributes first
    name = comp.get("Name") or comp.get("name") or ""
    firstname = comp.get("FirstName") or comp.get("firstname") or ""
    if not name and not firstname:
        full = _get_competitor_fullname(comp)
        if full:
            surname, fname = split_athlete_name(full)
            name, firstname = surname, fname

    result.athlete_name = name
    result.athlete_firstname = firstname
    result.club = comp.get("Club") or comp.get("club") or comp.get("c") or ""
    result.category = comp.get("Category") or comp.get("category") or comp.get("ca") or ""
    result.gender = comp.get("Gender") or comp.get("gender") or comp.get("x") or ""
    # v = overall rank in ChronoSmetron E format; Rank/rank in Competitor format
    result.rank_overall = normalize_rank(
        comp.get("Rank") or comp.get("rank") or comp.get("v")
    )
    result.rank_category = normalize_rank(
        comp.get("CategoryRank") or comp.get("categoryrank")
    )
    result.rank_gender = normalize_rank(
        comp.get("GenderRank") or comp.get("genderrank")
    )
    result.total_time = normalize_time(comp.get("Time") or comp.get("time") or "")

    stages = comp.findall(".//SplitTime") + comp.findall(".//Stage")
    raw: dict = {}
    for s in stages:
        sname = (s.get("Name") or s.get("name") or "").lower()
        stime = normalize_time(s.get("Time") or s.get("time") or "")
        raw[f"split_{sname}"] = stime
        if "swim" in sname or "natation" in sname or "nage" in sname:
            if not result.swim_time:
                result.swim_time = stime
        elif "t1" in sname:
            if not result.t1_time:
                result.t1_time = stime
        elif "bike" in sname or "velo" in sname or "vélo" in sname or "cycle" in sname:
            if not result.bike_time:
                result.bike_time = stime
        elif "t2" in sname:
            if not result.t2_time:
                result.t2_time = stime
        elif "run" in sname or "cap" in sname or "course" in sname:
            if not result.run_time:
                result.run_time = stime

    result.raw_data = raw
    return result


def _resolve_to_wiclax_url(url: str, client: httpx.Client) -> str:
    """
    Resolve various Wiclax-family URL formats to a usable URL:
    - chronosmetron.com event pages → extract wiclax-results.com link
    - wiclax-results.com directory pages → extract G-Live iframe src
    """
    resp = client.get(url, headers=HEADERS)
    resp.raise_for_status()

    # chronosmetron.com: find the wiclax-results.com results link in href attribute
    if "chronosmetron.com" in url and "wiclax-results.com" not in url:
        from urllib.parse import quote
        m = re.search(r'href=["\']([^"\']*wiclax-results\.com/[^"\']+)["\']', resp.text, re.I)
        if m:
            raw = m.group(1).strip()
            # URL-encode spaces in the path
            parsed_raw = urlparse(raw)
            encoded_path = quote(parsed_raw.path, safe="/%+")
            found = parsed_raw._replace(path=encoded_path).geturl().rstrip("/") + "/"
            return _resolve_to_wiclax_url(found, client)
        raise ValueError(f"Aucun lien de résultats Wiclax trouvé sur : {url}")

    # wiclax-results.com directory: extract G-Live iframe src
    m = re.search(r'<iframe[^>]+src=["\']([^"\']+g-live\.html[^"\']*)["\']', resp.text, re.I)
    if m:
        src = m.group(1)
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return urljoin(base, src)

    raise ValueError(f"Impossible de trouver le lien G-Live dans la page Wiclax : {url}")


def _fetch_clax(url: str) -> tuple[ET.Element, str, str, str, object]:
    """
    Fetch and parse a .clax XML file from a Wiclax G-Live URL.
    Directory URLs (no f= param) are resolved via iframe extraction first.
    Returns (root, clax_url, event_name, event_type, event_date).
    """
    from datetime import date as date_t

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        # Resolve chronosmetron.com or directory URLs to G-Live URL if needed
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if not params.get("f") or "chronosmetron.com" in url and "wiclax-results.com" not in url:
            url = _resolve_to_wiclax_url(url, client)
            parsed = urlparse(url)
            params = parse_qs(parsed.query)

        f_param = params.get("f", [""])[0]
        base = f"{parsed.scheme}://{parsed.netloc}"
        glive_dir = "/G-Live/"
        clax_url = urljoin(base + glive_dir, f_param)

        resp = client.get(clax_url, headers=HEADERS)
        resp.raise_for_status()
        xml_content = resp.text

    root = ET.fromstring(xml_content)
    event_elem = root.find(".//Event") or root.find(".//RACE") or root
    event_name = (
        event_elem.get("Name", "")
        or event_elem.get("name", "")
        or unquote(f_param).split("/")[-1].replace(".clax", "")
    )
    event_type = _detect_event_type(event_name)

    event_date = None
    dt1 = event_elem.get("dt1", "") or event_elem.get("Dt1", "") or event_elem.get("date", "")
    if dt1:
        try:
            event_date = date_t.fromisoformat(dt1[:10])
        except ValueError:
            pass

    return root, clax_url, event_name, event_type, event_date


def _get_competitor_fullname(comp) -> str:
    """Extract full name from a competitor element (handles both XML formats)."""
    # Format 1: Competitor/Runner with Name + FirstName attributes
    name = comp.get("Name") or comp.get("name") or ""
    firstname = comp.get("FirstName") or comp.get("firstname") or ""
    if name or firstname:
        return re.sub(r"\s+", " ", f"{firstname} {name}").strip()
    # Format 2: TimePulse/Wiclax E element with n="Firstname\xa0SURNAME"
    n = comp.get("n") or comp.get("N") or ""
    return re.sub(r"[\s\xa0]+", " ", n).strip()


def _get_competitor_bib(comp) -> str:
    return (comp.get("Bib") or comp.get("bib") or
            comp.get("d") or comp.get("D") or "")


def _build_split_indices(root: ET.Element) -> dict[str, int]:
    """
    Parse <Segments><S> definitions to build a dynamic sN-key mapping.

    Each <S> element's 0-based position in the list is its sN index.
    Segments are classified by disc and trans attributes:
      disc=5, trans absent → swim
      disc=-1, trans=1     → transition (first=T1, second=T2)
      disc=0               → bike
      disc=6               → run

    We identify TOTAL segments (not individual laps) by matching
    checkpoint ranges: total segment spans T1_end→T2_start (bike) or
    T2_end→finish (run).
    """
    segs_elem = root.find(".//Segments")
    if segs_elem is None:
        return {}

    segments = list(segs_elem)
    result: dict[str, int] = {}

    # Find T1 and T2 (first two elements with trans=1)
    t1_ptg1 = t1_ptg2 = t2_ptg1 = t2_ptg2 = None
    trans_found = 0
    for i, s in enumerate(segments):
        if s.get("trans") == "1":
            if trans_found == 0:
                result["t1"] = i
                t1_ptg1, t1_ptg2 = s.get("ptg1"), s.get("ptg2")
            elif trans_found == 1:
                result["t2"] = i
                t2_ptg1, t2_ptg2 = s.get("ptg1"), s.get("ptg2")
            trans_found += 1
            if trans_found == 2:
                break

    # Swim total: disc=5, ptg1=-999, ptg2 = t1_ptg1 (ends exactly where T1 starts)
    for i, s in enumerate(segments):
        if s.get("disc") == "5" and s.get("ptg1") == "-999":
            if t1_ptg1 is None or s.get("ptg2") == t1_ptg1:
                result["swim"] = i
                break

    # Bike total: disc=0, spans exactly from T1_end to T2_start
    if t1_ptg2 and t2_ptg1:
        for i, s in enumerate(segments):
            if (s.get("disc") == "0"
                    and s.get("ptg1") == t1_ptg2
                    and s.get("ptg2") == t2_ptg1):
                result["bike"] = i
                break

    # Run total: disc=6, starts exactly where T2 ends, goes to finish (ptg2=999)
    if t2_ptg2:
        for i, s in enumerate(segments):
            if (s.get("disc") == "6"
                    and s.get("ptg1") == t2_ptg2
                    and s.get("ptg2") == "999"):
                result["run"] = i
                break

    return result


def _fill_er_splits(
    result_elem: ET.Element,
    r: ScrapedResult,
    split_idx: dict[str, int],
) -> None:
    """Fill split times on r from a ChronoSmetron R element using split_idx."""
    def get(key: str) -> str:
        n = split_idx.get(key)
        return normalize_time(result_elem.get(f"s{n}", "")) if n is not None else ""

    if split_idx:
        r.swim_time = get("swim")
        r.t1_time   = get("t1")
        r.bike_time = get("bike")
        r.t2_time   = get("t2")
        r.run_time  = get("run")
    else:
        # Fallback when no <Segments> definition found (older events)
        r.swim_time = normalize_time(result_elem.get("s2", ""))
        r.t1_time   = normalize_time(result_elem.get("s3", ""))
        r.bike_time = normalize_time(result_elem.get("s4", ""))
        r.t2_time   = normalize_time(result_elem.get("s5", ""))
        r.run_time  = normalize_time(result_elem.get("s10", ""))


def _search_in_xml(root, search: str) -> list:
    """Return competitor elements whose name matches search (all words, any order)."""
    words = re.sub(r"[\s\xa0]+", " ", search).strip().upper().split()
    if not words:
        return []

    def matches_words(full: str) -> bool:
        full_up = full.upper()
        return all(w in full_up for w in words)

    matches = []
    # Format 1: Competitor/Runner tags
    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        for comp in root.iter(tag):
            if matches_words(_get_competitor_fullname(comp)):
                matches.append(comp)
    # Format 2: TimePulse-style E elements
    if not matches:
        for comp in root.iter("E"):
            if matches_words(_get_competitor_fullname(comp)):
                matches.append(comp)
    return matches


def scrape(url: str) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    bib = params.get("B", [""])[0] or params.get("b", [""])[0]
    search = params.get("search", [""])[0].strip()

    root, clax_url, event_name, event_type, event_date = _fetch_clax(url)
    split_idx = _build_split_indices(root)

    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=bib)
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date

    # Resolve bib from name search if needed
    if not bib and search:
        matches = _search_in_xml(root, search)
        if not matches:
            raise ValueError(
                f"Athlète « {search} » introuvable dans cet événement Wiclax."
            )
        if len(matches) > 1:
            candidates = []
            for comp in matches:
                full = _get_competitor_fullname(comp)
                surname, firstname = split_athlete_name(full)
                candidates.append({
                    "bib": _get_competitor_bib(comp),
                    "athlete_name": surname,
                    "athlete_firstname": firstname,
                    "total_time": normalize_time(comp.get("Time") or comp.get("time") or comp.get("t") or ""),
                    "club": comp.get("Club") or comp.get("club") or comp.get("c") or "",
                })
            raise MultipleMatchesError(candidates)
        bib = _get_competitor_bib(matches[0])
        result.bib_number = bib

    # Find competitor by bib
    competitor = None
    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        competitor = root.find(f".//{tag}[@Bib='{bib}']")
        if competitor is None:
            competitor = root.find(f".//{tag}[@bib='{bib}']")
        if competitor is not None:
            break

    if competitor is None:
        for comp in root.iter():
            if _get_competitor_bib(comp) == bib and bib:
                competitor = comp
                break

    raw: dict = {"bib": bib, "clax_url": clax_url}

    if competitor is not None:
        parsed_result = _parse_competitor(competitor, url, event_name, event_type)

        # ChronoSmetron E/R format: competitor is <E>, times are in a sibling <R d=bib>
        if competitor.tag == "E" and not parsed_result.total_time:
            result_elem = root.find(f".//R[@d='{bib}']")
            if result_elem is not None:
                raw.update(dict(result_elem.attrib))
                parsed_result.total_time = normalize_time(result_elem.get("t", ""))
                _fill_er_splits(result_elem, parsed_result, split_idx)

        # Copy all fields from parsed_result into result
        result.athlete_name = parsed_result.athlete_name
        result.athlete_firstname = parsed_result.athlete_firstname
        result.club = parsed_result.club
        result.category = parsed_result.category
        result.gender = parsed_result.gender
        result.rank_overall = parsed_result.rank_overall
        result.rank_category = parsed_result.rank_category
        result.rank_gender = parsed_result.rank_gender
        result.total_time = parsed_result.total_time
        result.swim_time = parsed_result.swim_time
        result.t1_time = parsed_result.t1_time
        result.bike_time = parsed_result.bike_time
        result.t2_time = parsed_result.t2_time
        result.run_time = parsed_result.run_time
        raw.update(parsed_result.raw_data)
        raw.update(dict(competitor.attrib))

    result.raw_data = raw
    return result


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """
    Fetch ALL participants from a Wiclax .clax event file.
    Uses a single HTTP request — the .clax XML contains all competitors.
    Handles both Competitor/Runner format and ChronoSmetron E/R format.
    """
    root, _clax_url, event_name, event_type, event_date = _fetch_clax(url)
    split_idx = _build_split_indices(root)
    # Strip the B= athlete-selector so each result links to the event, not a random athlete
    base_url = _strip_athlete_param(url)
    results: list[ScrapedResult] = []

    # Format 1: Competitor / Runner / Participant elements
    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        found = list(root.iter(tag))
        if found:
            for comp in found:
                bib = comp.get("Bib") or comp.get("bib") or ""
                if not bib:
                    continue
                r = _parse_competitor(comp, base_url, event_name, event_type)
                r.event_date = event_date
                results.append(r)
            break

    # Format 2: ChronoSmetron E/R elements (E = competitor, R = timing keyed by d=bib)
    if not results:
        r_by_bib: dict[str, ET.Element] = {
            elem.get("d", ""): elem
            for elem in root.iter("R")
            if elem.get("d")
        }
        for comp in root.iter("E"):
            bib = _get_competitor_bib(comp)
            if not bib:
                continue
            r = _parse_competitor(comp, base_url, event_name, event_type)
            # Rank from v attribute on E element
            if comp.get("v") and not r.rank_overall:
                r.rank_overall = normalize_rank(comp.get("v"))
            # Timing from sibling R element
            result_elem = r_by_bib.get(bib)
            if result_elem is not None and not r.total_time:
                r.total_time = normalize_time(result_elem.get("t", ""))
                _fill_er_splits(result_elem, r, split_idx)
            r.event_date = event_date
            results.append(r)

    return results


def _strip_athlete_param(url: str) -> str:
    """Remove the B= (athlete selector) parameter from a Wiclax G-Live URL."""
    parsed = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parsed.query).items() if k.upper() != "B"}
    return urlunparse(parsed._replace(query=urlencode(params)))



def _detect_event_type(name: str) -> str:
    n = name.lower().strip()
    if "xxl" in n or "ironman" in n or "longue distance" in n or n.endswith(" xl") or " xl " in n:
        return "triathlon-xl"
    if "longue" in n or " l " in n or n.endswith(" l") or "half" in n or "70.3" in n:
        return "triathlon-l"
    if "olympique" in n or "olympic" in n or " m " in n or n.endswith(" m") or "triathlon-m" in n:
        return "triathlon-m"
    if "sprint" in n or " s " in n or n.endswith(" s") or " s-" in n or "triathlon-s" in n:
        return "triathlon-s"
    if "xs" in n:
        return "triathlon-s"
    if "duathlon" in n:
        return "duathlon"
    if "swimrun" in n or "swim-run" in n or "swim run" in n:
        return "swimrun"
    return "triathlon"
