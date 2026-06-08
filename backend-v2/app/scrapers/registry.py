"""
Registre des providers de chronométrage.

Chaque provider est une instance implémentant `ScraperProtocol`. La détection se
fait en parcourant la liste `PROVIDERS` (plus de chaîne de `if/else`). Ajouter un
provider = créer son adapter et l'ajouter à la liste, à un seul endroit.

Provider inconnu → fallback Playwright.

NOTE — La factorisation des helpers internes communs (`_detect_event_type`,
mapping des splits) entre klikego/wiclax/timepulse reste un refacto à part : ces
fonctions ont des signatures divergentes et wiclax n'a pas de tests, donc on évite
de les fusionner ici au risque d'une régression silencieuse. Voir le design.
"""
import logging
from typing import Protocol, runtime_checkable
from urllib.parse import parse_qs, urlparse

from app.scrapers import (
    breizhchrono,
    klikego,
    prolivesport,
    sportinnovation,
    timepulse,
    wiclax,
)
from app.scrapers.base import ScrapedResult

logger = logging.getLogger(__name__)


@runtime_checkable
class ScraperProtocol(Protocol):
    """Contrat que tout provider doit respecter."""

    name: str

    def matches(self, url: str) -> bool:
        """Vrai si ce provider sait traiter l'URL."""
        ...

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        """Scrape tous les participants de l'épreuve (peut lever ValueError si non supporté)."""
        ...


class KlikegoProvider:
    name = "klikego"

    def matches(self, url: str) -> bool:
        return "klikego.com" in url

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        path_parts = [p for p in parsed.path.strip("/").split("/") if p]
        event_id = path_parts[-1] if path_parts else ""
        heat = params.get("heat", [""])[0]
        slug = path_parts[-2] if len(path_parts) >= 2 else ""
        event_name = slug.replace("-", " ").title() if slug else ""
        if not heat:
            # Auto-détection du heat via le helper klikego
            import httpx

            from app.scrapers.klikego import HEADERS as KL_HEADERS
            from app.scrapers.klikego import _detect_heat
            with httpx.Client(follow_redirects=True, timeout=20, headers=KL_HEADERS) as client:
                heat = _detect_heat(event_id, client)
        return klikego.scrape_event_all(event_id, heat, event_name, slug)


class BreizhChronoProvider:
    name = "breizhchrono"

    def matches(self, url: str) -> bool:
        return "breizhchrono.com" in url

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        from app.scrapers.breizhchrono import _parse_bc_url

        if "live.breizhchrono.com" in urlparse(url).netloc:
            raise ValueError(
                "Les liens live.breizhchrono.com ne sont pas supportés. "
                "Rendez-vous sur resultats.breizhchrono.com pour récupérer le lien de résultats."
            )
        event_id, heat, slug = _parse_bc_url(url)
        event_name = slug.replace("-", " ").title() if slug else ""
        return breizhchrono.scrape_event_all(event_id, heat, event_name, slug)


class WiclaxProvider:
    name = "wiclax"

    def matches(self, url: str) -> bool:
        return (
            "wiclax-results.com" in url
            or ("wiclax.com" in url and "G-Live" in url)
            or "chronosmetron.com" in url
        )

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return wiclax.scrape_event_all(url)


class TimePulseProvider:
    name = "timepulse"

    def matches(self, url: str) -> bool:
        return "timepulse.fr" in url

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return timepulse.scrape_event_all(url)


class ProLiveSportProvider:
    name = "prolivesport"

    def matches(self, url: str) -> bool:
        return "prolivesport.fr" in url

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return prolivesport.scrape_event_all(url)


class SportInnovationProvider:
    name = "sportinnovation"

    def matches(self, url: str) -> bool:
        return "sportinnovation.fr" in url

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        return sportinnovation.scrape_event_all(url)


class PlaywrightProvider:
    """Fallback générique pour les sites JS-heavy non reconnus."""

    name = "playwright"

    def matches(self, url: str) -> bool:
        return True  # capte tout ce qui n'a pas été reconnu avant

    def scrape_event_all(self, url: str) -> list[ScrapedResult]:
        raise ValueError(
            "Import de tous les participants non supporté pour ce provider : playwright"
        )


# Ordre important : breizhchrono et wiclax avant klikego (conditions plus spécifiques).
PROVIDERS: list[ScraperProtocol] = [
    BreizhChronoProvider(),
    WiclaxProvider(),
    KlikegoProvider(),
    TimePulseProvider(),
    ProLiveSportProvider(),
    SportInnovationProvider(),
]
_FALLBACK: ScraperProtocol = PlaywrightProvider()


def _find_provider(url: str) -> ScraperProtocol:
    for provider in PROVIDERS:
        if provider.matches(url):
            return provider
    return _FALLBACK


def detect_provider(url: str) -> str:
    return _find_provider(url).name


def scrape_event_all(url: str) -> list[ScrapedResult]:
    provider = _find_provider(url)
    logger.info("Import épreuve via %s : %s", provider.name, url)
    return provider.scrape_event_all(url)
