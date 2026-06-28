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

from app.scrapers import breizhchrono, klikego, registry

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


@pytest.mark.integration
def test_prolivesport_includes_non_finishers():
    """prolivesport renvoie désormais finishers ET non-finishers, chacun statué."""
    url = LIVE_URLS["prolivesport"]
    results = registry.scrape_event_all(url)
    assert results, "prolivesport : aucun participant renvoyé"
    statuses = {r.status for r in results}
    assert "finisher" in statuses, "prolivesport : aucun finisher"
    assert any(s != "finisher" for s in statuses), (
        f"prolivesport : aucun non-finisher (statuts vus : {statuses})"
    )
    # Un non-finisher n'a ni temps total ni rang.
    for r in results:
        if r.status != "finisher":
            assert not r.total_time, f"{r.status} avec un temps total : {r.total_time}"
            assert r.rank_overall is None, f"{r.status} avec un rang : {r.rank_overall}"


@pytest.mark.integration
def test_timepulse_conserve_non_finishers():
    """Le fix TimePulse conserve les non-finishers s'il y en a (best-effort).

    Données réelles évolutives → pas d'assertion stricte sur le nombre. On vérifie
    que des finishers remontent et on documente le nombre de non-finishers
    conservés (un <E> sans <R> → total_time vide).
    """
    results = registry.scrape_event_all(LIVE_URLS["timepulse"])
    assert results, "timepulse : aucun participant"
    assert any(r.total_time for r in results), "timepulse : aucun finisher"
    non_finishers = [r for r in results if not r.total_time]
    print(
        f"timepulse non-finishers conservés : {len(non_finishers)}/{len(results)}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("provider, url", sorted(LIVE_URLS.items()))
def test_scrape_event_all_status_jamais_incoherent(provider, url):
    """Garde-fou : un résultat avec statut non-finisher n'a pas de temps total.

    Vérifie l'hygiène cross-provider (DNF/DNS/DSQ ⇒ total_time vide).
    """
    results = registry.scrape_event_all(url)
    for r in results:
        if r.status in ("DNF", "DNS", "DSQ"):
            assert not r.total_time, (
                f"{provider} : {r.athlete_name} statut {r.status} mais temps {r.total_time!r}"
            )


@pytest.mark.integration
def test_bc_audencia_la_baule_exhaustif():
    results = breizhchrono.scrape_event_all(
        "1488071608761-572", "triathlon-s-light",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
    )
    assert len(results) == 591
    assert sum(1 for r in results if not r.status) == 483       # finishers
    assert sum(1 for r in results if r.status == "DNF") >= 1
    assert sum(1 for r in results if r.status == "DNS") >= 1
    # splits inter présents pour les finishers (event avec checkpoints)
    assert any(r.bike_time for r in results if not r.status)


@pytest.mark.integration
def test_klikego_nozeen_exhaustif():
    results = klikego.scrape_event_all(
        "1517534975128-8", "duathlon-s---open",
        "6e Duathlon Nozeen 2026", "6e-duathlon-nozeen-2026",
    )
    assert len(results) == 166
    assert sum(1 for r in results if r.status == "DNF") == 27
