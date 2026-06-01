from .base import ScrapedResult
from . import breizhchrono, wiclax, klikego, timepulse, playwright_fallback


def detect_provider(url: str) -> str:
    if "breizhchrono.com" in url:
        return "breizhchrono"
    if "wiclax-results.com" in url or ("wiclax.com" in url and "G-Live" in url):
        return "wiclax"
    if "klikego.com" in url:
        return "klikego"
    if "timepulse.fr" in url:
        return "timepulse"
    return "playwright"


def scrape(url: str) -> ScrapedResult:
    provider = detect_provider(url)
    if provider == "breizhchrono":
        return breizhchrono.scrape(url)
    if provider == "wiclax":
        return wiclax.scrape(url)
    if provider == "klikego":
        return klikego.scrape(url)
    if provider == "timepulse":
        return timepulse.scrape(url)
    return playwright_fallback.scrape(url)


__all__ = ["ScrapedResult", "detect_provider", "scrape"]
