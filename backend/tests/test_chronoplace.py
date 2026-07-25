"""
Tests unitaires pour scrapers/chronoplace.py (sans réseau).

Les fixtures sont des extraits réels du site (2026-07-25), réduits à quelques
lignes : structure conditionnelle Livewire et `wire:snapshot` conservés tels quels.
"""
from pathlib import Path

import httpx
import pytest

from app.scrapers import chronoplace

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_494 = _fixture("chronoplace_epreuve_494.html")   # triathlon S, splits
EPREUVE_566 = _fixture("chronoplace_epreuve_566.html")   # swimrun, catégories relais
EPREUVE_493 = _fixture("chronoplace_epreuve_493.html")   # 24h VTT, isTeam
RECHERCHE_2025 = _fixture("chronoplace_recherche_2025.html")  # annuaire, porteur des dates


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


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les fixtures et enregistre les URLs demandées."""

    def __init__(self, pages: dict[str, str] | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>404</html>", 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, page in self.pages.items():
            if motif in url:
                return page if isinstance(page, FakeResponse) else FakeResponse(page)
        return self.defaut


def test_fetch_renvoie_le_html():
    client = FakeClient({"/classement/": EPREUVE_494})
    assert chronoplace._fetch(client, "/classement/x/epreuve/1") == EPREUVE_494
    assert client.calls == ["https://www.chronoplace.fr/classement/x/epreuve/1"]


def test_fetch_404_leve_une_erreur_explicite():
    """Le site exige la paire slug + id exacte : un slug obsolète renvoie 404."""
    client = FakeClient()
    with pytest.raises(ValueError, match="slug obsolète ou épreuve retirée"):
        chronoplace._fetch(client, "/classement/spay-swimrun-2025/epreuve/566")


def test_fetch_erreur_serveur_remonte():
    client = FakeClient(defaut=FakeResponse("", 500))
    with pytest.raises(httpx.HTTPError):
        chronoplace._fetch(client, "/classement/x/epreuve/1")


def test_parse_event_date_depuis_la_carte_de_levenement():
    from datetime import date

    assert chronoplace._parse_event_date(RECHERCHE_2025, "spaycific-races-2025") == date(2025, 9, 21)
    assert chronoplace._parse_event_date(RECHERCHE_2025, "sitrans-bike-run-de-leves-2025") == (
        date(2025, 12, 14)
    )


def test_parse_event_date_slug_absent():
    assert chronoplace._parse_event_date(RECHERCHE_2025, "un-evenement-inconnu-2025") is None


def test_parse_event_date_repli_texte_francais():
    """Si l'attribut `datetime` manque ou est illisible, on parse le texte affiché."""
    from datetime import date

    html = """
    <article><div>
      <time datetime="">21 septembre 2025</time>
      <a href="/classement/spaycific-races-2025/epreuve/494">Voir</a>
    </div></article>
    """
    assert chronoplace._parse_event_date(html, "spaycific-races-2025") == date(2025, 9, 21)


def test_fetch_event_date_interroge_lannuaire_filtre():
    from datetime import date

    client = FakeClient({"/recherche": RECHERCHE_2025})
    resultat = chronoplace._fetch_event_date(client, "spaycific-races-2025", "2025", "Triathlon")

    assert resultat == date(2025, 9, 21)
    assert client.calls == [
        "https://www.chronoplace.fr/recherche?module=classement&annee=2025&categorie=12"
    ]


def test_fetch_event_date_categorie_inconnue_ne_requete_pas():
    """La date est un bonus : une catégorie hors table ne coûte pas une requête."""
    client = FakeClient({"/recherche": RECHERCHE_2025})
    assert chronoplace._fetch_event_date(client, "x-2025", "2025", "Pétanque") is None
    assert client.calls == []


def test_fetch_event_date_annuaire_en_erreur():
    client = FakeClient(defaut=FakeResponse("", 500))
    assert chronoplace._fetch_event_date(client, "x-2025", "2025", "Triathlon") is None


def _resultats(html: str, slug: str, event_date=None):
    return chronoplace._epreuve_results(html, "https://exemple/url-demandee", slug, event_date)


def test_epreuve_results_triathlon():
    from datetime import date

    resultats = _resultats(EPREUVE_494, "spaycific-races-2025", date(2025, 9, 21))

    assert len(resultats) == 3
    tcn = resultats[1]
    assert tcn.provider == "chronoplace"
    assert tcn.source_url == "https://exemple/url-demandee"
    assert (tcn.athlete_name, tcn.athlete_firstname) == ("MASHAYEKHI", "Sherwin")
    assert tcn.bib_number == "49"
    assert tcn.club == "TRIATHLON CLUB NANTAIS"
    assert tcn.gender == "M"
    assert tcn.rank_overall == 8
    assert tcn.total_time == "01:06:55"
    assert tcn.event_name == "Spay'cific Races 2025 - Spay'cific Triathlon S"
    assert tcn.event_type == "triathlon-s"
    assert tcn.event_date == date(2025, 9, 21)
    assert tcn.is_relay is False


def test_epreuve_results_splits_dans_les_slots_positionnels():
    """Les 5 slots triathlon sont ré-étiquetés par sport dans services/mapping."""
    premier = _resultats(EPREUVE_494, "spaycific-races-2025")[0]

    assert premier.swim_time == "00:10:53"
    assert premier.t1_time == "00:00:48"
    assert premier.bike_time == "00:31:01"
    assert premier.t2_time == "00:00:52"
    assert premier.run_time == "00:04:33"


def test_epreuve_results_splits_absents_rendus_en_tiret():
    """Ligne réelle : splits non chronométrés (« — »), temps total présent."""
    sans_splits = _resultats(EPREUVE_494, "spaycific-races-2025")[2]

    assert sans_splits.total_time == "01:30:44"
    assert (sans_splits.swim_time, sans_splits.bike_time, sans_splits.run_time) == ("", "", "")


def test_epreuve_results_le_scraper_ne_se_prononce_pas_sur_le_statut():
    """Aucun label DNF/DNS/DSQ observé : on laisse mapping.derive_status décider."""
    assert all(r.status == "" for r in _resultats(EPREUVE_494, "spaycific-races-2025"))


def test_epreuve_results_relais_detecte_par_la_categorie():
    resultats = _resultats(EPREUVE_566, "spaycific-races-2025")

    assert [r.is_relay for r in resultats] == [False, True, True]
    assert resultats[1].category == "Relais Mixte"
    assert resultats[0].event_type == "swimrun"


def test_epreuve_results_nom_dequipe_limite_connue():
    """`split_athlete_name` coupe un nom d'équipe au premier jeton non capitalisé.

    Comportement hérité de TimePulse, verrouillé ici volontairement : on reste
    cohérent avec les autres providers plutôt que d'inventer une règle locale.
    """
    relais = _resultats(EPREUVE_566, "spaycific-races-2025")[1]

    assert relais.athlete_name == "MENARDAIS FERDINAND"
    assert relais.athlete_firstname == "/ COMPAIN LENA"


def test_epreuve_results_is_team_du_snapshot():
    """24 h VTT : `isTeam:true`, aucune colonne catégorie — le relais vient du snapshot."""
    resultats = _resultats(EPREUVE_493, "24h-vtt-de-cergy-2025")

    assert all(r.is_relay for r in resultats)
    assert resultats[0].athlete_name == "CREPHAISSON"
    assert resultats[0].category == ""
    assert resultats[0].gender == ""


def test_epreuve_results_duree_superieure_a_24h():
    assert _resultats(EPREUVE_493, "24h-vtt-de-cergy-2025")[1].total_time == "24:00:13"


def test_epreuve_results_raw_data_conserve_toutes_les_cellules():
    """`nb_tours` et `ecart` ne sont ni temps ni split : ils ne vivent que là."""
    relais = _resultats(EPREUVE_566, "spaycific-races-2025")[1]

    assert relais.raw_data["nb_tours"] == "15"
    assert relais.raw_data["ecart"] == "+5:16"
    assert relais.raw_data["temps"] == "02:05:37"


def test_build_result_sans_colonne_dossard():
    """Certaines épreuves n'affichent pas le dossard : pas de KeyError, champ vide."""
    resultat = chronoplace._build_result(
        {"position": "1", "nom": "ONICOACH", "temps": "05:54:28"},
        url="u", event_name="E", event_type="triathlon", event_date=None, is_team=True,
    )

    assert resultat.bib_number == ""
    assert resultat.club == ""
    assert resultat.rank_overall == 1
    assert resultat.is_relay is True
