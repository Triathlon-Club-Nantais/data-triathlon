"""
Registre des scrapers.

L'API publique (`detect_provider`, `scrape_event_all`, `ScrapedResult`) est exposée
par `registry.py` — un registre de providers basé sur un Protocol, sans chaîne de
`if/else`. Seule voie de scraping : l'import d'épreuve complète (`scrape_event_all`).
"""
from app.scrapers.base import ScrapedResult
from app.scrapers.registry import detect_provider, scrape_event_all

__all__ = [
    "ScrapedResult",
    "detect_provider",
    "scrape_event_all",
]
