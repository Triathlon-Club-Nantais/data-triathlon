"""
Tests d'intégration des scrapers — appels réseau RÉELS (marker `integration`).

Hors CI par défaut. Lancer explicitement :
    pytest -m integration

Vérifie la voie unique `scrape_event_all` sur une épreuve réelle par provider.
Les URLs (événements passés/stables) sont documentées dans
`docs/superpowers/specs/2026-06-08-scrapers-audit-report.md`.

Assertions volontairement souples (les données d'épreuve évoluent) : le scraper
doit renvoyer ≥1 participant avec au moins un nom et un temps total peuplés.
"""
import pytest

from app.scrapers import registry

# URLs réelles fonctionnelles, une par provider.
# prolivesport : forme front `/result/{eventId}/{index}` (l'index 6 = course "S").
LIVE_URLS = {
    "klikego": "https://www.klikego.com/resultats/triathlon-de-vierzon-2026/1674523163798-4",
    "breizhchrono": (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
    ),
    "wiclax": "https://chronosmetron.wiclax-results.com/Triathlon%20de%20la%20Roche%202026/",
    "timepulse": "https://www.timepulse.fr/epreuves/resultats/live/3232",
    "prolivesport": "https://www.prolivesport.fr/result/1082/6",
    "sportinnovation": "https://sportinnovation.fr/Evenements/Resultats/7031",
}


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_detection(provider, url):
    """L'URL est routée vers le bon provider."""
    assert registry.detect_provider(url) == provider


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_scrape_event_all_live(provider, url):
    """L'import d'épreuve renvoie des participants exploitables."""
    results = registry.scrape_event_all(url)
    assert results, f"{provider} : aucun participant renvoyé"
    assert any(r.athlete_name for r in results), f"{provider} : aucun nom d'athlète"
    assert any(r.total_time for r in results), f"{provider} : aucun temps total"
    # Type d'épreuve détecté sur au moins un résultat
    assert any(r.event_type for r in results), f"{provider} : type d'épreuve non détecté"


@pytest.mark.integration
def test_sportinnovation_2026_race_url():
    """Forme 2026 results.sportinnovation.fr/race/{slug} (niveau course, API JSON)."""
    url = "https://results.sportinnovation.fr/race/zmhc-triathlon-m"
    results = registry.scrape_event_all(url)
    assert results
    assert any(r.athlete_name and r.total_time for r in results)
    assert any(r.event_type for r in results)
