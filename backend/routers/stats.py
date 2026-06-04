"""
Aggregated statistics and event geolocation endpoints.
"""
import re
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from database import get_db
from models import Result

router = APIRouter()

_TCN_KEYWORDS = ("nantais", "tcn", "triathlon club nant")

# ── In-memory geocode cache (reset on server restart) ────────────────────────
_geo_cache: dict[str, Optional[tuple[float, float]]] = {}
_GEO_HEADERS = {"User-Agent": "TriathlonClubResults/1.0 contact@triclunantais.fr"}


def _extract_city(event_name: str) -> str:
    """
    Extract a searchable city/location from a French triathlon event name.
    Examples:
      "Triathlon de la Roche"  → "la Roche"
      "DUATHLON COUERON"       → "COUERON"
      "Swimrun des 20 plages de Pornichet à Saint-Nazaire" → "Pornichet"
      "Triathlon Châtelaillon Plage 2026" → "Châtelaillon Plage"
    """
    name = event_name.strip()

    # Remove trailing year/edition markers
    name = re.sub(r"\b(20\d{2}|[0-9]+e?\s+edition)\b", "", name, flags=re.I).strip()
    name = re.sub(r"[-–—]+$", "", name).strip()

    # Remove common prefix words for triathlon/multisport events
    prefixes = (
        r"(triathlon|tri|duathlon|swimrun|swim[- ]?run|aquathlon|aquarun|bike[- ]?run"
        r"|run[- ]?bike|challenge|ironman|half|ultra|trail)\s+"
        r"(de\s+la\s+|de\s+le\s+|des\s+|de\s+|du\s+|d['']\s*|international\s+)?"
        r"(la\s+|le\s+|les\s+|saint[-\s]|sainte[-\s])?"
    )
    cleaned = re.sub(prefixes, "", name, flags=re.I).strip()

    # Remove format suffixes (S, M, L, XL, XS, Sprint, Olympique…)
    cleaned = re.sub(
        r"\s+(s|m|l|xl|xs|xxl|sprint|olympique|olympic|half|longue|distance|format)\s*$",
        "", cleaned, flags=re.I
    ).strip()

    # Remove numbers like "20 plages", "8km", "24h"
    cleaned = re.sub(r"\b\d+[\s\-]?(plages?|km|h)\b", "", cleaned, flags=re.I).strip()

    # Keep first meaningful segment (before " à ", " –", " -")
    cleaned = re.split(r"\s+[àa]\s+|\s+[-–]\s+", cleaned)[0].strip()

    return cleaned or event_name


def _nominatim_search(query: str) -> Optional[tuple[float, float]]:
    """Single Nominatim call; returns (lat, lon) of the most important hit, or None."""
    try:
        r = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "json", "limit": 5,
                    "countrycodes": "fr"},
            headers=_GEO_HEADERS,
            timeout=5,
        )
        results = r.json()
        time.sleep(1.1)  # Nominatim rate limit: max 1 req/s
        # Filter to place/boundary types only; pick highest importance
        places = [x for x in results if x.get("class") in ("place", "boundary", "administrative")]
        hits = places or results
        if hits:
            # importance is a float 0-1; sort descending and take best
            hits.sort(key=lambda x: float(x.get("importance", 0)), reverse=True)
            return (float(hits[0]["lat"]), float(hits[0]["lon"]))
    except Exception:
        pass
    return None


def _geocode(event_name: str) -> Optional[tuple[float, float]]:
    """Geocode an event name to (lat, lon) using Nominatim. Rate-limited to 1 req/s."""
    if event_name in _geo_cache:
        return _geo_cache[event_name]

    city = _extract_city(event_name)
    if not city or len(city) < 3:
        _geo_cache[event_name] = None
        return None

    # Strategy 1: extracted city name
    coord = _nominatim_search(f"{city}, France")

    # Strategy 2: if city extraction changed the name, try the full event name too
    if coord is None and city.lower() != event_name.lower():
        coord = _nominatim_search(f"{event_name}, France")

    _geo_cache[event_name] = coord
    return coord


# ── /api/stats ────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    club: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Return aggregated club statistics."""
    q = db.query(Result)
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        q = q.filter(or_(*[Result.club.ilike(f"%{k}%") for k in keywords]))

    results = q.all()
    if not results:
        return {"total": 0, "athletes": 0, "events": 0, "by_type": {}, "by_month": {}, "recent": []}

    athlete_set = {f"{r.athlete_name}||{r.athlete_firstname}" for r in results}
    event_set   = {r.event_name for r in results if r.event_name}

    by_type: dict[str, int] = {}
    by_month: dict[str, int] = {}

    for r in results:
        if r.event_type:
            by_type[r.event_type] = by_type.get(r.event_type, 0) + 1
        if r.event_date:
            key = str(r.event_date)[:7]  # "YYYY-MM"
            by_month[key] = by_month.get(key, 0) + 1

    # 20 most recent
    recent = sorted(
        [r for r in results if r.scraped_at],
        key=lambda r: r.scraped_at,
        reverse=True,
    )[:20]

    return {
        "total":    len(results),
        "athletes": len(athlete_set),
        "events":   len(event_set),
        "by_type":  dict(sorted(by_type.items(), key=lambda x: -x[1])),
        "by_month": dict(sorted(by_month.items())),
        "recent": [
            {
                "id":               r.id,
                "athlete_name":     r.athlete_name or "",
                "athlete_firstname":r.athlete_firstname or "",
                "club":             r.club or "",
                "event_name":       r.event_name or "",
                "event_type":       r.event_type or "",
                "event_date":       r.event_date.isoformat() if r.event_date else None,
                "total_time":       r.total_time or "",
                "scraped_at":       r.scraped_at.isoformat() if r.scraped_at else None,
            }
            for r in recent
        ],
    }


# ── /api/stats/events-geo ─────────────────────────────────────────────────────

@router.get("/stats/events-geo")
def get_events_geo(
    club: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Return geocoded event locations for the heatmap.
    Groups results by event_name, returns {event_name, lat, lon, count, tcn_count}.
    Geocoding is cached in memory after first call.
    """
    from sqlalchemy import case
    tcn_conds = or_(*[Result.club.ilike(f"%{k}%") for k in _TCN_KEYWORDS])
    q = db.query(
        Result.event_name,
        Result.event_date,
        Result.event_type,
        func.count(Result.id).label("total"),
        func.sum(case((tcn_conds, 1), else_=0)).label("tcn_count"),
    )
    if club:
        keywords = [k.strip() for k in club.split("|") if k.strip()]
        q = q.filter(or_(*[Result.club.ilike(f"%{k}%") for k in keywords]))

    rows = (
        q.group_by(Result.event_name, Result.event_date, Result.event_type)
        .order_by(func.count(Result.id).desc())
        .all()
    )

    geo_events = []
    for row in rows:
        if not row.event_name:
            continue
        coord = _geocode(row.event_name)
        if coord:
            geo_events.append({
                "event_name": row.event_name,
                "event_date": row.event_date.isoformat() if row.event_date else None,
                "event_type": row.event_type or "",
                "count":      row.total,
                "tcn_count":  int(row.tcn_count or 0),
                "lat":        coord[0],
                "lon":        coord[1],
            })

    return geo_events
