"""
Tests unitaires pour scrapers/chronoplace.py (sans réseau).

Les fixtures sont des extraits réels du site (2026-07-25), réduits à quelques
lignes : structure conditionnelle Livewire et `wire:snapshot` conservés tels quels.
"""
from pathlib import Path

import pytest

from app.scrapers import chronoplace

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_494 = _fixture("chronoplace_epreuve_494.html")   # triathlon S, splits
EPREUVE_566 = _fixture("chronoplace_epreuve_566.html")   # swimrun, catégories relais
EPREUVE_493 = _fixture("chronoplace_epreuve_493.html")   # 24h VTT, isTeam


def test_parse_url_avec_epreuve():
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "494")


def test_parse_url_slug_seul():
    """URL sans /epreuve/<id> : acceptée, l'id sera résolu par une requête."""
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "")


def test_parse_url_ignore_la_query_string():
    slug, epreuve_id = chronoplace._parse_url(
        "https://www.chronoplace.fr/classement/spaycific-races-2025/epreuve/494?perPage=all"
    )
    assert (slug, epreuve_id) == ("spaycific-races-2025", "494")


def test_parse_url_rejette_une_page_hors_classement():
    with pytest.raises(ValueError, match="non reconnue"):
        chronoplace._parse_url("https://www.chronoplace.fr/recherche?module=classement")


def test_epreuve_path_force_le_classement_complet():
    """`perPage=all` est ce qui fait passer de 50 lignes au classement entier."""
    assert chronoplace._epreuve_path("spaycific-races-2025", "494") == (
        "/classement/spaycific-races-2025/epreuve/494?perPage=all"
    )


def test_parse_snapshot_deballe_les_tableaux_livewire():
    """Livewire sérialise une liste en `[valeur, {"s": "arr"}]` → on prend l'élément 0."""
    data = chronoplace._parse_snapshot(EPREUVE_494)

    assert data["epreuveId"] == 494
    assert data["isTeam"] is False
    assert data["analyticsContext"]["epreuve_name"] == "Spay'cific Triathlon S"
    assert data["analyticsContext"]["event_year"] == "2025"
    assert data["affichageDonnees"]["T_natation"] is True


def test_parse_snapshot_is_team():
    assert chronoplace._parse_snapshot(EPREUVE_493)["isTeam"] is True


def test_parse_snapshot_page_sans_composant():
    assert chronoplace._parse_snapshot("<html><body>rien</body></html>") == {}


def test_parse_snapshot_json_illisible():
    assert chronoplace._parse_snapshot('<div wire:snapshot="{pas du json">x</div>') == {}
