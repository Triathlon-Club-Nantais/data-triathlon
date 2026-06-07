"""
Registre des scrapers.

L'API publique (`detect_provider`, `scrape`, `scrape_event_all`, `ScrapedResult`,
`MultipleMatchesError`) est exposée par `registry.py` — un registre de providers
basé sur un Protocol, sans chaîne de `if/else`.
"""
from app.scrapers.base import MultipleMatchesError, ScrapedResult
from app.scrapers.registry import detect_provider, scrape, scrape_event_all

__all__ = [
    "ScrapedResult",
    "MultipleMatchesError",
    "detect_provider",
    "scrape",
    "scrape_event_all",
]
