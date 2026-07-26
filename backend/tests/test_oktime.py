"""
Tests unitaires pour scrapers/oktime.py (sans réseau).

Les fixtures sont des charges API réduites, calquées sur le schéma mesuré au
panel du 2026-07-26 (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md).
Le schéma réel est revérifié par le test `integration` sur l'événement 48555.
"""
import pytest

from app.scrapers import oktime


def test_parse_url_forme_classement():
    """`classement.ok-time.fr/<id>` : l'id du chemin EST le post-id WordPress."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555") == ("48555", "")


def test_parse_url_ignore_le_segment_race():
    """L'API ne sait pas filtrer par épreuve : `/race/<id>` est sans effet."""
    assert oktime._parse_url("https://classement.ok-time.fr/48555/race/59697") == ("48555", "")


def test_parse_url_tolere_le_slash_final():
    assert oktime._parse_url("https://classement.ok-time.fr/48555/") == ("48555", "")


def test_parse_url_forme_evenement_rend_le_slug():
    """La forme éditoriale n'expose pas l'id : il faudra une requête pour le lire."""
    assert oktime._parse_url("https://ok-time.fr/evenement/triathlon-de-lacanau-2026/") == (
        "",
        "triathlon-de-lacanau-2026",
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://ok-time.fr/course/format-s-individuel-3/",
        "https://ok-time.fr/competition/t24-ile-de-re-2025/",
        "https://ok-time.fr/course/triathlon-l/",
    ],
)
def test_parse_url_rejette_les_formes_obsoletes(url):
    """Les 3 URLs mortes du Sheet : erreur qualifiée, pour se lire sans enquête.

    ok-time devenant un host supporté, elles quittent `ignored_by_host` et
    deviennent des épreuves en erreur dans les bilans CLI (§2.1 du design). Le
    message doit dire pourquoi.
    """
    with pytest.raises(ValueError, match="obsolète"):
        oktime._parse_url(url)


def test_parse_url_rejette_une_page_hors_resultats():
    with pytest.raises(ValueError, match="non reconnue"):
        oktime._parse_url("https://ok-time.fr/contact/")
