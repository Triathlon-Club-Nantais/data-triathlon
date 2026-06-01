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



def scrape(url: str) -> ScrapedResult:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    f_param = params.get("f", [""])[0]  # relative path to .clax file
    bib = params.get("B", [""])[0]

    base = f"{parsed.scheme}://{parsed.netloc}"
    # Build absolute URL to the .clax XML file
    # f_param is like "../Triathlon de la Roche 2026/Triathlon de la Roche.clax"
    # The G-Live page is at /G-Live/g-live.html
    glive_dir = "/G-Live/"
    clax_url = urljoin(base + glive_dir, f_param)

    with httpx.Client(follow_redirects=True, timeout=30) as client:
        resp = client.get(clax_url, headers=HEADERS)
        resp.raise_for_status()
        xml_content = resp.text

    root = ET.fromstring(xml_content)
    result = ScrapedResult(source_url=url, provider="wiclax", bib_number=bib)

    # Event info
    event_elem = root.find(".//Event") or root.find(".//RACE") or root
    result.event_name = (
        event_elem.get("Name", "")
        or event_elem.get("name", "")
        or unquote(f_param).split("/")[-1].replace(".clax", "")
    )
    result.event_type = _detect_event_type(result.event_name)

    # Find competitor by bib
    competitor = None
    for tag in ("Competitor", "COMPETITOR", "Runner", "RUNNER", "Participant"):
        competitor = root.find(f".//{tag}[@Bib='{bib}']")
        if competitor is None:
            competitor = root.find(f".//{tag}[@bib='{bib}']")
        if competitor is not None:
            break

    if competitor is None:
        # Fallback: search all competitors
        for comp in root.iter():
            if comp.get("Bib") == bib or comp.get("bib") == bib:
                competitor = comp
                break

    raw: dict = {"bib": bib, "clax_url": clax_url}

    if competitor is not None:
        raw.update(dict(competitor.attrib))

        name = competitor.get("Name") or competitor.get("name") or ""
        firstname = competitor.get("FirstName") or competitor.get("firstname") or ""
        if not name and not firstname:
            full = competitor.get("FullName") or competitor.get("fullname") or ""
            parts = full.split()
            name = parts[0] if parts else ""
            firstname = " ".join(parts[1:]) if len(parts) > 1 else ""

        result.athlete_name = name
        result.athlete_firstname = firstname
        result.club = competitor.get("Club") or competitor.get("club") or ""
        result.category = competitor.get("Category") or competitor.get("category") or ""
        result.gender = competitor.get("Gender") or competitor.get("gender") or ""
        result.rank_overall = normalize_rank(competitor.get("Rank") or competitor.get("rank"))
        result.rank_category = normalize_rank(
            competitor.get("CategoryRank") or competitor.get("categoryrank")
        )
        result.rank_gender = normalize_rank(
            competitor.get("GenderRank") or competitor.get("genderrank")
        )
        result.total_time = normalize_time(competitor.get("Time") or competitor.get("time") or "")

        # Split times — look for SplitTime or Stage children
        stages = competitor.findall(".//SplitTime") + competitor.findall(".//Stage")
        stage_names = []
        for s in stages:
            sname = (s.get("Name") or s.get("name") or "").lower()
            stime = normalize_time(s.get("Time") or s.get("time") or "")
            raw[f"split_{sname}"] = stime
            stage_names.append((sname, stime))

        for sname, stime in stage_names:
            if "swim" in sname or "natation" in sname or "nage" in sname:
                result.swim_time = stime
            elif "t1" in sname:
                result.t1_time = stime
            elif "bike" in sname or "velo" in sname or "vélo" in sname or "cycle" in sname:
                result.bike_time = stime
            elif "t2" in sname:
                result.t2_time = stime
            elif "run" in sname or "cap" in sname or "course" in sname:
                result.run_time = stime

    result.raw_data = raw
    return result


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
