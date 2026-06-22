"""
Géocodage des épreuves via Nominatim (OpenStreetMap).

Extraction de la ville depuis le nom d'épreuve français, puis recherche Nominatim
avec cache mémoire et respect du rate-limit (1 req/s).
"""
import logging
import re
import time

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

# Cache mémoire (réinitialisé au redémarrage du serveur)
_geo_cache: dict[str, tuple[float, float] | None] = {}


def extract_city(event_name: str) -> str:
    """Extrait une ville/localité cherchable depuis un nom d'épreuve triathlon français."""
    name = event_name.strip()
    name = re.sub(r"\b(20\d{2}|[0-9]+e?\s+edition)\b", "", name, flags=re.I).strip()
    name = re.sub(r"[-–—]+$", "", name).strip()

    prefixes = (
        r"(triathlon|tri|duathlon|swimrun|swim[- ]?run|aquathlon|aquarun|bike[- ]?run"
        r"|run[- ]?bike|challenge|ironman|half|ultra|trail)\s+"
        r"(de\s+la\s+|de\s+le\s+|des\s+|de\s+|du\s+|d['']\s*|international\s+)?"
        r"(la\s+|le\s+|les\s+|saint[-\s]|sainte[-\s])?"
    )
    cleaned = re.sub(prefixes, "", name, flags=re.I).strip()
    cleaned = re.sub(
        r"\s+(s|m|l|xl|xs|xxl|sprint|olympique|olympic|half|longue|distance|format)\s*$",
        "", cleaned, flags=re.I,
    ).strip()
    cleaned = re.sub(r"\b\d+[\s\-]?(plages?|km|h)\b", "", cleaned, flags=re.I).strip()
    cleaned = re.split(r"\s+[àa]\s+|\s+[-–]\s+", cleaned)[0].strip()
    return cleaned or event_name


def _nominatim_search(query: str) -> tuple[float, float] | None:
    """Un appel Nominatim ; renvoie (lat, lon) du résultat le plus pertinent, ou None."""
    settings = get_settings()
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 5, "countrycodes": "fr"},
            headers={"User-Agent": settings.geocode_user_agent},
            timeout=5,
        )
        results = r.json()
        time.sleep(settings.geocode_min_interval_seconds)  # rate limit Nominatim
        places = [
            x for x in results if x.get("class") in ("place", "boundary", "administrative")
        ]
        hits = places or results
        if hits:
            hits.sort(key=lambda x: float(x.get("importance", 0)), reverse=True)
            return (float(hits[0]["lat"]), float(hits[0]["lon"]))
    except Exception as exc:
        logger.warning("Géocodage échoué pour « %s » : %s", query, exc)
    return None


def geocode(event_name: str) -> tuple[float, float] | None:
    """Géocode un nom d'épreuve en (lat, lon). Résultat mis en cache mémoire."""
    if event_name in _geo_cache:
        return _geo_cache[event_name]

    city = extract_city(event_name)
    if not city or len(city) < 3:
        _geo_cache[event_name] = None
        return None

    coord = _nominatim_search(f"{city}, France")
    if coord is None and city.lower() != event_name.lower():
        coord = _nominatim_search(f"{event_name}, France")

    _geo_cache[event_name] = coord
    return coord
