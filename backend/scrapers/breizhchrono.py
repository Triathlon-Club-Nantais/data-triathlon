"""
Scraper for resultats.breizhchrono.com
URL example:
  https://resultats.breizhchrono.com/bc/resultats/coureur.jsp
    ?ref=1700025627600-3&heat=triathlon-s-individuel&dossard=194
"""
import re
from urllib.parse import urlparse, parse_qs

import httpx
from bs4 import BeautifulSoup

from .base import ScrapedResult
from .utils import normalize_time, normalize_rank


def _safe_int(value: str) -> int | None:
    return normalize_rank(value)


def scrape(url: str) -> ScrapedResult:
    params = parse_qs(urlparse(url).query)
    heat = params.get("heat", [""])[0]
    dossard = params.get("dossard", [""])[0]

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        )
    }

    with httpx.Client(follow_redirects=True, timeout=20) as client:
        resp = client.get(url, headers=headers)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    result = ScrapedResult(source_url=url, provider="breizhchrono")

    # Event name — look for h1/h2
    title_tag = soup.find("h1") or soup.find("h2")
    if title_tag:
        result.event_name = title_tag.get_text(strip=True)

    # Detect event type from heat param
    result.event_type = _detect_event_type(heat)
    result.bib_number = dossard

    # Tables — first table usually has athlete info / results
    tables = soup.find_all("table")
    raw: dict = {"heat": heat, "dossard": dossard}

    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            key = cells[0].lower()
            val = cells[1] if len(cells) > 1 else ""
            raw[key] = val

            if "nom" in key or "name" in key:
                parts = val.split()
                if parts:
                    result.athlete_name = parts[0]
                    result.athlete_firstname = " ".join(parts[1:])
            elif "prénom" in key or "prenom" in key:
                result.athlete_firstname = val
            elif "club" in key:
                result.club = val
            elif "catégorie" in key or "categorie" in key or "cat." in key:
                result.category = val
            elif "sexe" in key or "genre" in key:
                result.gender = "F" if "f" in val.lower() else "M"
            elif "classement général" in key or "rang général" in key or "position" in key:
                result.rank_overall = _safe_int(val)
            elif "classement catégorie" in key or "rang cat" in key:
                result.rank_category = _safe_int(val)
            elif "classement sexe" in key or "rang sexe" in key:
                result.rank_gender = _safe_int(val)
            elif "temps total" in key or "total" in key:
                result.total_time = normalize_time(val)
            elif "natation" in key or "swim" in key or "nage" in key:
                result.swim_time = normalize_time(val)
            elif "t1" in key:
                result.t1_time = normalize_time(val)
            elif "vélo" in key or "velo" in key or "bike" in key or "cyclisme" in key:
                result.bike_time = normalize_time(val)
            elif "t2" in key:
                result.t2_time = normalize_time(val)
            elif "cap" in key or "course à pied" in key or "run" in key:
                result.run_time = normalize_time(val)

    result.raw_data = raw
    return result


def _detect_event_type(heat: str) -> str:
    heat = heat.lower()
    if "xxl" in heat or "ironman" in heat:
        return "triathlon-xl"
    if "-l" in heat or "triathlon-l" in heat or "long" in heat:
        return "triathlon-l"
    if "-m" in heat or "triathlon-m" in heat or "olymp" in heat:
        return "triathlon-m"
    if "-s" in heat or "triathlon-s" in heat or "sprint" in heat:
        return "triathlon-s"
    if "duathlon" in heat:
        return "duathlon"
    if "swimrun" in heat or "swim-run" in heat:
        return "swimrun"
    return heat
