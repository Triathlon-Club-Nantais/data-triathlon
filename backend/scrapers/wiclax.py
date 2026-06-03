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
from urllib.parse import urljoin, urlparse, parse_qs, unquote

import httpx

from .base import ScrapedResult
from .utils import normalize_time, normalize_rank

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}



def _parse_competitor(comp, url: str, event_name: str, event_type: str) -> ScrapedResult:
    """Build a ScrapedResult from a single competitor XML element."""
    bib = comp.get("Bib") or comp.get("bib") or ""
    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=bib)
    result.event_name = event_name
    result.event_type = event_type

    name = comp.get("Name") or comp.get("name") or ""
    firstname = comp.get("FirstName") or comp.get("firstname") or ""
    if not name and not firstname:
        full = comp.get("FullName") or comp.get("fullname") or ""
        parts = full.split()
        name = parts[0] if parts else ""
        firstname = " ".join(parts[1:]) if len(parts) > 1 else ""

    result.athlete_name = name
    result.athlete_firstname = firstname
    result.club = comp.get("Club") or comp.get("club") or ""
    result.category = comp.get("Category") or comp.get("category") or ""
    result.gender = comp.get("Gender") or comp.get("gender") or ""
    result.rank_overall = normalize_rank(comp.get("Rank") or comp.get("rank"))
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


def _fetch_clax(url: str) -> tuple[ET.Element, str, str, str, object]:
    """
    Fetch and parse a .clax XML file from a Wiclax G-Live URL.
    Returns (root, clax_url, event_name, event_type, event_date).
    """
    from datetime import date as date_t
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    f_param = params.get("f", [""])[0]
    base = f"{parsed.scheme}://{parsed.netloc}"
    glive_dir = "/G-Live/"
    clax_url = urljoin(base + glive_dir, f_param)

    with httpx.Client(follow_redirects=True, timeout=30) as client:
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


def scrape(url: str) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    f_param = params.get("f", [""])[0]
    bib = params.get("B", [""])[0]

    root, clax_url, event_name, event_type, event_date = _fetch_clax(url)

    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=bib)
    result.event_name = event_name
    result.event_type = event_type
    result.event_date = event_date

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
            if comp.get("Bib") == bib or comp.get("bib") == bib:
                competitor = comp
                break

    raw: dict = {"bib": bib, "clax_url": clax_url}

    if competitor is not None:
        parsed_result = _parse_competitor(competitor, url, event_name, event_type)
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
    """
    root, _clax_url, event_name, event_type, event_date = _fetch_clax(url)
    results: list[ScrapedResult] = []

    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        found = list(root.iter(tag))
        if found:
            for comp in found:
                bib = comp.get("Bib") or comp.get("bib") or ""
                if not bib:
                    continue
                r = _parse_competitor(comp, url, event_name, event_type)
                r.event_date = event_date
                results.append(r)
            break

    return results


def _detect_event_type(name: str) -> str:
    name = name.lower()
    if "xxl" in name or "ironman" in name or "longue distance" in name:
        return "triathlon-xl"
    if "longue" in name or " l " in name or "half" in name or "70.3" in name:
        return "triathlon-l"
    if "olympique" in name or "olympic" in name or " m " in name or "triathlon-m" in name:
        return "triathlon-m"
    if "sprint" in name or " s " in name or "triathlon-s" in name:
        return "triathlon-s"
    if "duathlon" in name:
        return "duathlon"
    if "swimrun" in name or "swim-run" in name or "swim run" in name:
        return "swimrun"
    return "triathlon"
