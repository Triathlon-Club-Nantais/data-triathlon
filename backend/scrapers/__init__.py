from .base import ScrapedResult
from . import breizhchrono, wiclax, klikego, timepulse, prolivesport, sportinnovation, playwright_fallback


def detect_provider(url: str) -> str:
    if "breizhchrono.com" in url:
        return "breizhchrono"
    if "wiclax-results.com" in url or ("wiclax.com" in url and "G-Live" in url):
        return "wiclax"
    if "chronosmetron.com" in url:
        return "wiclax"
    if "klikego.com" in url:
        return "klikego"
    if "timepulse.fr" in url:
        return "timepulse"
    if "prolivesport.fr" in url:
        return "prolivesport"
    if "sportinnovation.fr" in url:
        return "sportinnovation"
    return "playwright"


def scrape(url: str, bib: str | None = None) -> ScrapedResult:
    provider = detect_provider(url)
    if provider == "breizhchrono":
        return breizhchrono.scrape(url, bib=bib)
    if provider == "wiclax":
        return wiclax.scrape(url)        # wiclax résout le bib via ?B= dans l'URL
    if provider == "klikego":
        return klikego.scrape(url, bib=bib)
    if provider == "timepulse":
        return timepulse.scrape(url)     # timepulse résout le bib via ?bib= dans l'URL
    if provider == "prolivesport":
        return prolivesport.scrape(url, bib=bib)
    if provider == "sportinnovation":
        return sportinnovation.scrape(url, bib=bib)
    return playwright_fallback.scrape(url)


def scrape_event_all(url: str) -> list[ScrapedResult]:
    """
    Fetch ALL participants for an event from the given results URL.
    Supported providers: klikego, breizhchrono, timepulse, wiclax,
                         prolivesport, sportinnovation.
    """
    from urllib.parse import urlparse, parse_qs

    provider = detect_provider(url)

    if provider == "klikego":
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        event_id = path_parts[-1] if path_parts else ""
        heat = params.get("heat", [""])[0]
        slug = path_parts[-2] if len(path_parts) >= 2 else ""
        event_name = slug.replace("-", " ").title() if slug else ""
        if not heat:
            # Auto-detect heat (reuse klikego helper)
            from .klikego import _detect_heat
            import httpx
            from .klikego import HEADERS as KL_HEADERS, BASE as KL_BASE
            with httpx.Client(follow_redirects=True, timeout=20, headers=KL_HEADERS) as client:
                heat = _detect_heat(event_id, client)
        return klikego.scrape_event_all(event_id, heat, event_name, slug)

    if provider == "breizhchrono":
        from .breizhchrono import _parse_bc_url
        from urllib.parse import urlparse as _urlparse
        if "live.breizhchrono.com" in _urlparse(url).netloc:
            raise ValueError(
                "Les liens live.breizhchrono.com ne sont pas supportés. "
                "Rendez-vous sur resultats.breizhchrono.com pour récupérer le lien de résultats."
            )
        event_id, heat, slug = _parse_bc_url(url)
        event_name = slug.replace("-", " ").title() if slug else ""
        return breizhchrono.scrape_event_all(event_id, heat, event_name, slug)

    if provider == "timepulse":
        return timepulse.scrape_event_all(url)

    if provider == "wiclax":
        return wiclax.scrape_event_all(url)

    if provider == "prolivesport":
        return prolivesport.scrape_event_all(url)

    if provider == "sportinnovation":
        return sportinnovation.scrape_event_all(url)

    raise ValueError(
        f"Import de tous les participants non supporté pour ce provider : {provider}"
    )


__all__ = ["ScrapedResult", "detect_provider", "scrape", "scrape_event_all"]
