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


def test_parse_table_lit_les_colonnes_par_cle():
    """Le `temps` est la dernière colonne, après les splits : lire par position casserait."""
    rows = chronoplace._parse_table(EPREUVE_494)

    assert len(rows) == 3
    assert rows[0] == {
        "position": "1",
        "dossard": "90",
        "nom": "MARTIN Malo",
        "genre": "M",
        "club": "ENTENTE HAUTE BRETAGNE TRIATHLON",
        "T_natation": "00:10:53",
        "T1": "00:00:48",
        "T_velo": "00:31:01",
        "T2": "00:00:52",
        "T_course_a_pied": "00:04:33",
        "temps": "01:01:26",
    }


def test_parse_table_colonnes_differentes_selon_lepreuve():
    """Le swimrun n'a ni genre ni club, mais une catégorie, un nb de tours et un écart."""
    rows = chronoplace._parse_table(EPREUVE_566)

    assert len(rows) == 3
    assert set(rows[0]) == {"position", "dossard", "nom", "categorie", "nb_tours", "temps", "ecart"}
    assert rows[1]["categorie"] == "Relais Mixte"
    assert rows[1]["ecart"] == "+5:16"


def test_parse_table_epreuve_sans_dossard_ni_categorie():
    rows = chronoplace._parse_table(EPREUVE_493)

    assert [r["nom"] for r in rows] == ["CREPHAISSON", "LA ROUE LA VRAIE"]
    assert "categorie" not in rows[0]


def test_parse_table_page_sans_tableau():
    assert chronoplace._parse_table("<html><body>rien</body></html>") == []


def test_parse_table_ignore_une_ligne_desalignee():
    """Anomalie jamais observée sur les 4 épreuves sondées, mais on ne décale rien."""
    html = """
    <table>
      <thead><tr>
        <th wire:click="sortBy('position')">P</th>
        <th wire:click="sortBy('nom')">N</th>
      </tr></thead>
      <tbody>
        <tr><td>1</td><td>MARTIN Malo</td></tr>
        <tr><td colspan="2">Aucun résultat</td></tr>
      </tbody>
    </table>
    """
    rows = chronoplace._parse_table(html)

    assert rows == [{"position": "1", "nom": "MARTIN Malo"}]


@pytest.mark.parametrize(
    "brut, attendu",
    [
        ("00:10:53", "00:10:53"),
        ("5:16", "00:05:16"),        # MM:SS → HH:MM:SS
        ("24:00:13", "24:00:13"),    # 24h VTT : durée > 24 h conservée telle quelle
        ("—", ""),                   # cellule de split vide (tiret cadratin)
        ("--", ""),                  # écart nul
        ("+5:16", ""),               # écart : ni temps ni split
        ("", ""),
    ],
)
def test_time_or_empty(brut, attendu):
    assert chronoplace._time_or_empty(brut) == attendu


def test_event_name_depuis_le_h1():
    """Le nom de l'épreuve doit figurer dans le nom de Course : `uq_course_identity`
    porte sur (name, event_date, event_type, is_relay), donc deux épreuves d'un même
    événement classées dans le même type fusionneraient sous le seul nom d'événement."""
    assert chronoplace._event_name(EPREUVE_494, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - Spay'cific Triathlon S"
    )
    assert chronoplace._event_name(EPREUVE_566, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - SwimRun"
    )


def test_event_name_repli_meta_description():
    html = (
        '<html><head><meta name="description" '
        'content="Résultats Spay\'cific Races 2025 - SwimRun"></head><body></body></html>'
    )
    assert chronoplace._event_name(html, "spaycific-races-2025") == (
        "Spay'cific Races 2025 - SwimRun"
    )


def test_event_name_repli_slug():
    assert chronoplace._event_name("<html><body></body></html>", "spaycific-races-2025") == (
        "Spaycific Races 2025"
    )


def test_list_epreuves_donne_les_onglets_de_levenement():
    assert chronoplace._list_epreuves(EPREUVE_494, "spaycific-races-2025") == ["494", "566"]
    assert chronoplace._list_epreuves(EPREUVE_493, "24h-vtt-de-cergy-2025") == ["492", "493"]


def test_list_epreuves_ignore_les_autres_evenements():
    html = """
    <a href="/classement/spaycific-races-2025/epreuve/494">A</a>
    <a href="/classement/un-autre-evenement-2025/epreuve/777">B</a>
    <a href="/classement/spaycific-races-2025">C</a>
    """
    assert chronoplace._list_epreuves(html, "spaycific-races-2025") == ["494"]


def test_event_type_par_epreuve():
    """Le type se déduit du nom d'épreuve, pas de celui de l'événement : le swimrun
    de Spay'cific vit dans un événement typé « Triathlon » côté chronoplace."""
    analytics_tri = chronoplace._parse_snapshot(EPREUVE_494)["analyticsContext"]
    analytics_swimrun = chronoplace._parse_snapshot(EPREUVE_566)["analyticsContext"]

    assert chronoplace._event_type(analytics_tri, "") == "triathlon-s"
    assert analytics_swimrun["event_type"] == "Triathlon"
    assert chronoplace._event_type(analytics_swimrun, "") == "swimrun"


def test_event_type_repli_sur_le_contexte_puis_le_nom():
    assert chronoplace._event_type({"event_type": "Duathlon"}, "") == "duathlon"
    assert chronoplace._event_type({}, "Aquathlon de Spay") == "aquathlon"


@pytest.mark.parametrize(
    "categorie, attendu",
    [
        ("Relais Mixte", True),
        ("Duo Masculin", True),
        ("Équipe entreprise", True),
        ("Solo Homme", False),
        ("", False),
    ],
)
def test_is_relay_category(categorie, attendu):
    assert chronoplace._is_relay_category(categorie) is attendu
