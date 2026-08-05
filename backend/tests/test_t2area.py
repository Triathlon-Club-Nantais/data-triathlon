"""
Tests unitaires pour scrapers/t2area.py (sans réseau).

Les fixtures sont des extraits réels de fftri.t2area.com (2026-07-26), réduits à
quelques lignes ; les attributs purement décoratifs ont été retirés, la structure
(`#resultList`, en-tête à 10 colonnes, accordéon des fiches) est intacte.
"""
import logging
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import t2area
from app.scrapers.base import ScrapedResult

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_LABAULE = _fixture("t2area_epreuve_labaule_m.html")
EDITION_LABAULE = _fixture("t2area_edition_labaule_2022.html")     # triathlon M, clés bib-
EDITION_BOUCHET = _fixture("t2area_edition_bouchet_2025.html")     # clés licence FFTRI
EDITION_NEVERS = _fixture("t2area_edition_nevers_duathlon_2022.html")  # duathlon
FICHE_TRIATHLON = _fixture("t2area_fiche_triathlon.html")
FICHE_DUATHLON = _fixture("t2area_fiche_duathlon.html")

# Fiche au découpage inattendu : `_appliquer_splits` doit basculer sur `segments`.
FICHE_LIBELLE_INCONNU = """
<html lang="fr"><body>
<ul class="accordion"><li class="accordion__item"><button><span>
<span class="title">Général</span><span class="title">01:00:00</span>
</span></button></li><li class="accordion__item"><button><span>
<span class="title">Natation 1</span><span class="title">00:10:00</span>
</span></button></li><li class="accordion__item"><button><span>
<span class="title">Trail 1</span><span class="title">00:20:00</span>
</span></button></li></ul>
</body></html>
"""

URL_EDITION = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"
)
URL_FICHE = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"
)
URL_EPREUVE = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m.html"
URL_EVENEMENT = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule.html"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les fixtures et enregistre les URLs demandées."""

    def __init__(
        self,
        pages: dict[str, str | FakeResponse] | None = None,
        defaut: FakeResponse | None = None,
    ):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>vide</html>")
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


def test_parse_url_edition():
    assert t2area._parse_url(URL_EDITION) == ("triathlon-de-la-baule", "triathlon-m", "2022")


def test_parse_url_tronque_une_fiche_individuelle():
    """Le cas réel du Sheet : un lien de fiche pointe l'édition qui la contient."""
    assert t2area._parse_url(URL_FICHE) == ("triathlon-de-la-baule", "triathlon-m", "2022")


def test_parse_url_epreuve_sans_annee():
    assert t2area._parse_url(URL_EPREUVE) == ("triathlon-de-la-baule", "triathlon-m", "")


def test_parse_url_refuse_un_evenement():
    """Les épreuves d'un événement ont des dernières éditions d'années différentes."""
    with pytest.raises(ValueError, match="pointez une épreuve"):
        t2area._parse_url(URL_EVENEMENT)


def test_parse_url_refuse_un_autre_host():
    with pytest.raises(ValueError, match="hors fftri.t2area.com"):
        t2area._parse_url("https://autre.t2area.com/calendrier/x/y/2022.html")


def test_parse_url_refuse_une_page_hors_calendrier():
    with pytest.raises(ValueError, match="non reconnue"):
        t2area._parse_url("https://fftri.t2area.com/clubs/triathlon-club-nantais.html")


def test_parse_url_refuse_une_annee_illisible():
    with pytest.raises(ValueError, match="Année illisible"):
        t2area._parse_url(
            "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/saison.html"
        )


def test_parse_url_refuse_une_profondeur_inconnue():
    with pytest.raises(ValueError, match="non reconnue"):
        t2area._parse_url(
            "https://fftri.t2area.com/calendrier/a/b/2022/bib-1/extra.html"
        )


def test_edition_url():
    assert t2area._edition_url("triathlon-de-la-baule", "triathlon-m", "2022") == URL_EDITION


def test_epreuve_url():
    assert t2area._epreuve_url("triathlon-de-la-baule", "triathlon-m") == URL_EPREUVE


def test_resolve_annee_prend_la_plus_recente():
    """La page d'épreuve liste toutes ses éditions ; la dernière est la plus récente."""
    client = FakeClient({"/triathlon-m.html": EPREUVE_LABAULE})

    assert t2area._resolve_annee(client, "triathlon-de-la-baule", "triathlon-m") == "2022"
    assert client.calls == [URL_EPREUVE]


def test_resolve_annee_sans_edition_leve():
    """Épreuve créée mais jamais courue : erreur explicite, pas de classement vide."""
    client = FakeClient({"/triathlon-m.html": "<html><body>rien</body></html>"})

    with pytest.raises(ValueError, match="Aucune édition publiée"):
        t2area._resolve_annee(client, "triathlon-de-la-baule", "triathlon-m")


def test_fetch_erreur_serveur_remonte():
    client = FakeClient(defaut=FakeResponse("", 500))
    with pytest.raises(httpx.HTTPError):
        t2area._fetch(client, URL_EDITION)


def _labaule() -> list:
    return t2area._parse_edition(
        EDITION_LABAULE, URL_EDITION, "triathlon-de-la-baule", "triathlon-m"
    )


def _par_nom(resultats, nom):
    return next(r for r in resultats if r.athlete_name.startswith(nom))


def test_parse_edition_lit_toutes_les_lignes():
    assert len(_labaule()) == 6


def test_parse_edition_colonnes_dun_finisher():
    r = _par_nom(_labaule(), "ACCENT")

    assert (r.athlete_name, r.athlete_firstname) == ("ACCENT", "Baptiste")
    assert r.club == "TRIATHLON CLUB NANTAIS"
    assert r.category == "MS2"
    assert r.gender == "M"
    assert r.rank_overall == 453
    assert r.rank_category == 89
    assert r.rank_gender is None
    assert r.total_time == "02:41:52"
    assert r.bib_number == "566"
    assert r.status == ""          # finisher : laissé à l'heuristique de mapping
    assert r.is_relay is False
    assert r.provider == "t2area"
    assert r.source_url == URL_EDITION


def test_parse_edition_entete_nom_et_date():
    """Nom et date viennent du <h1> ; la date entre dans l'identité de la Course."""
    r = _labaule()[0]

    assert r.event_name == "Triathlon de La Baule - M"
    assert r.event_date == date(2022, 9, 18)
    assert r.event_type == "triathlon-m"


def test_parse_edition_classement_feminin_rempli_pour_les_femmes():
    """`Clt/F` n'est renseigné que sur les lignes féminines (125/125 sur l'épreuve réelle)."""
    r = _par_nom(_labaule(), "ANTOINE")

    assert r.gender == "F"
    assert r.rank_gender == 80


def test_parse_edition_dnf():
    """Un DNF sort avec `00:00:00` dans la colonne Temps : c'est un temps absent."""
    r = _par_nom(_labaule(), "EPP")

    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None


def test_parse_edition_disqualifie():
    r = _par_nom(_labaule(), "ALLARD")

    assert r.status == "DSQ"
    assert r.rank_overall is None


def test_parse_edition_disqualifie_navance_pas_de_temps():
    """La FFTRI publie parfois un temps sur un DSQ (`42:23:00`, ALLARD Pierre) :
    invariant du dépôt, un non-finisher n'a pas de temps total. Le brut reste
    diagnosticable dans `raw_data`."""
    r = _par_nom(_labaule(), "ALLARD")

    assert r.status == "DSQ"
    assert r.total_time == ""
    assert r.rank_gender is None
    assert r.rank_category is None
    assert r.raw_data["temps"] == "42:23:00"


def test_construire_disqualifie_vide_aussi_les_rangs_meme_si_publies():
    """Sur la ligne ALLARD réelle, `Clt/F` et `Clt/CAT` sont vides — insuffisant
    pour attester que le vidage est actif plutôt que fortuit. Ligne synthétique
    avec des rangs catégorie/genre **renseignés** malgré un statut DSQ : ils
    doivent être vidés au même titre que `total_time` (wiclax fait de même)."""
    ligne = {
        "clt": "DQ",
        "clt_f": "3",
        "temps": "42:23:00",
        "nom": "ALLARD Pierre",
        "club": "INDIV LIGUE PAYS DE LA LOIRE",
        "cat": "MVE",
        "clt_cat": "5",
        "id_league": "28",
        "league": "",
        "details_href": "",
        "club_href": "",
    }

    r = t2area._construire(
        ligne,
        source_url=URL_EDITION,
        evenement="triathlon-de-la-baule",
        epreuve="triathlon-m",
        event_name="Triathlon de La Baule - M",
        event_type="triathlon-m",
        event_date=date(2022, 9, 18),
        chrono=("", ""),
    )

    assert r.status == "DSQ"
    assert r.total_time == ""
    assert r.rank_gender is None
    assert r.rank_category is None


def test_parse_edition_club_absent():
    assert _par_nom(_labaule(), "AGIS").club == ""


def test_parse_edition_ligne_anonyme_du_site():
    """« 907 Dossard » : une entrée sans identité, telle que la source la publie.

    Aucune heuristique locale — le scraper ne devine pas d'identité. Test de
    verrouillage : le jour où on voudra changer ça, ce sera un choix explicite.
    """
    r = _par_nom(_labaule(), "Dossard")

    assert (r.athlete_name, r.athlete_firstname) == ("Dossard", "907")
    assert r.bib_number == "907"


def test_parse_edition_raw_data_conserve_le_contexte():
    r = _par_nom(_labaule(), "ACCENT")

    assert r.raw_data["cle_fiche"] == "bib-566"
    assert r.raw_data["league"] == "PAYS DE LA LOIRE"
    assert r.raw_data["id_league"] == "15"
    assert r.raw_data["club_href"] == "/clubs/triathlon-club-nantais.html"
    assert r.raw_data["clt"] == "453"
    assert r.raw_data["fiche_url"].endswith("/2022/bib-566.html")


def test_parse_edition_cle_licence_ne_remplit_pas_le_dossard():
    """`bib_number` ne contient jamais autre chose qu'un vrai dossard (§2.3)."""
    resultats = t2area._parse_edition(
        EDITION_BOUCHET,
        "https://fftri.t2area.com/calendrier/triathlon-du-lac-du-bouchet/triathlon-l/2025.html",
        "triathlon-du-lac-du-bouchet",
        "triathlon-l",
    )
    r = _par_nom(resultats, "ABRANTES")

    assert r.bib_number == ""
    assert r.raw_data["cle_fiche"] == "A44719"
    assert r.event_name == "Triathlon du Lac du Bouchet (43) - L"
    assert r.event_date == date(2025, 7, 13)
    assert r.event_type == "triathlon-l"


def test_parse_edition_duathlon():
    resultats = t2area._parse_edition(
        EDITION_NEVERS,
        "https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022.html",
        "triathlon-de-nevers",
        "duathlon-m",
    )

    assert len(resultats) == 3
    assert {r.event_type for r in resultats} == {"duathlon-m"}
    assert _par_nom(resultats, "PANNIER").rank_gender == 14


def test_parse_edition_sans_result_list_leve():
    """Édition inexistante : le site répond 303 vers son accueil, donc 200."""
    with pytest.raises(ValueError, match="Aucun classement"):
        t2area._parse_edition(
            "<html><body><h1>CALENDRIER DES ÉPREUVES FFTRI</h1></body></html>",
            URL_EDITION,
            "triathlon-de-la-baule",
            "triathlon-m",
        )


def test_parse_edition_entete_ampute_leve():
    """Markup changé : mieux vaut une erreur qu'un import silencieusement faux."""
    html = (
        "<html><body><h1>Résultats du X - 2022 - édition du 18-09-2022</h1>"
        '<table id="resultList"><thead><tr><th>Nom</th><th>Club</th></tr></thead>'
        "<tbody></tbody></table></body></html>"
    )
    with pytest.raises(ValueError, match="En-tête fftri inattendu"):
        t2area._parse_edition(html, URL_EDITION, "x", "triathlon-m")


def test_parse_edition_sans_details_leve():
    """`Détails` absente : sans lever, toutes les lignes sortiraient sans dossard
    ni fiche, et dupliqueraient chaque participation déjà en base (cf. #51)."""
    html = (
        "<html><body><h1>Résultats du X - 2022 - édition du 18-09-2022</h1>"
        '<table id="resultList"><thead><tr>'
        "<th>Clt</th><th>Temps</th><th>Nom</th><th>Club</th>"
        "</tr></thead><tbody></tbody></table></body></html>"
    )
    with pytest.raises(ValueError, match="En-tête fftri inattendu"):
        t2area._parse_edition(html, URL_EDITION, "x", "triathlon-m")


def test_index_colonnes_place_details_apres_les_colonnes_de_ligue():
    """L'en-tête réel porte 10 colonnes : `id_league`/`league` avant `Détails`.

    C'est pour ça qu'on lit par libellé et non par position.
    """
    from bs4 import BeautifulSoup

    table = BeautifulSoup(EDITION_LABAULE, "lxml").find(id="resultList")

    assert t2area._index_colonnes(table) == {
        "clt": 0, "clt_f": 1, "temps": 2, "nom": 3, "club": 4,
        "cat": 5, "clt_cat": 6, "id_league": 7, "league": 8, "details": 9,
    }


@pytest.mark.parametrize("brut,attendu", [
    ("02:41:52", "02:41:52"),
    ("00:00:00", ""),      # DNF : temps absent, pas un temps nul
    ("", ""),
    ("   ", ""),
])
def test_temps_ou_vide(brut, attendu):
    assert t2area._temps_ou_vide(brut) == attendu


@pytest.mark.parametrize("categorie,attendu", [
    ("MS2", "M"), ("FV1", "F"), ("MHAN", "M"), ("MT1", "M"), ("", ""), ("S3", ""),
])
def test_genre(categorie, attendu):
    assert t2area._genre(categorie) == attendu


@pytest.mark.parametrize("cle,attendu", [
    ("bib-566", "566"),
    ("A44719", ""),        # licence FFTRI
    ("id-1153352", ""),    # identifiant interne
    ("", ""),
])
def test_dossard(cle, attendu):
    assert t2area._dossard(cle) == attendu


@pytest.mark.parametrize("epreuve,attendu", [
    ("swim-run-m-eq", True),
    ("bike-run-s-open-eq", True),
    ("triathlon-jeunes-1-eq", True),
    ("triathlon-relais", True),
    ("triathlon-m", False),
    ("triathlon-s-open", False),
    ("duathlon-l", False),
])
def test_est_relais(epreuve, attendu):
    """Déduit du slug — non vérifié sur données réelles (§8.3 du design)."""
    assert t2area._est_relais(epreuve) is attendu


def test_entete_titre_illisible_garde_la_date():
    """Deux regex indépendantes : un libellé inattendu ne fait pas perdre la date."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(
        "<html><body><h1>Résultats — édition du 18-09-2022</h1></body></html>", "lxml"
    )
    nom, event_date = t2area._entete(soup, "triathlon-de-la-baule", "triathlon-m")

    assert event_date == date(2022, 9, 18)
    assert nom == "Triathlon De La Baule Triathlon M"


# Mention réelle de Vichy L 2024 : un chronométreur que nous savons lire.
EDITION_RACERESULT = EDITION_LABAULE.replace(
    '<a href="http://www.ipitos.com/">IPITOS </a>',
    '<a href="http://my3.raceresult.com/">RaceResult </a>',
)


def test_chronometreur_lit_la_mention():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(EDITION_LABAULE, "lxml")

    assert t2area._chronometreur(soup) == ("IPITOS", "http://www.ipitos.com/")


def test_chronometreur_absent():
    from bs4 import BeautifulSoup

    soup = BeautifulSoup("<html><body><p>rien</p></body></html>", "lxml")

    assert t2area._chronometreur(soup) == ("", "")


def test_chronometreur_dans_raw_data():
    r = _par_nom(_labaule(), "ACCENT")

    assert r.raw_data["chronometreur"] == "IPITOS"
    assert r.raw_data["chronometreur_url"] == "http://www.ipitos.com/"


def test_avertissement_quand_le_chronometreur_est_supporte(caplog):
    """L'opérateur doit savoir qu'une meilleure source existe — lui seul peut la fournir."""
    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        t2area._parse_edition(
            EDITION_RACERESULT, URL_EDITION, "triathlon-de-la-baule", "triathlon-m"
        )

    assert "raceresult" in caplog.text
    assert "my3.raceresult.com" in caplog.text


def test_pas_davertissement_pour_un_chronometreur_non_supporte(caplog):
    """IPITOS est hors de notre périmètre : rien à signaler, le scraper fait le travail."""
    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        _labaule()

    assert "IPITOS" not in caplog.text


def test_pas_davertissement_sans_mention(caplog):
    from bs4 import BeautifulSoup

    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        t2area._avertir_source_amont(*t2area._chronometreur(BeautifulSoup("", "lxml")), URL_EDITION)

    assert caplog.text == ""


def test_parse_fiche_triathlon_exclut_le_general():
    """« Général » est le temps total, déjà lu dans le classement."""
    segments = t2area._parse_fiche(FICHE_TRIATHLON)

    assert [libelle for libelle, _ in segments] == [
        "Natation", "Transition 1", "Vélo", "Transition 2", "Course à Pied",
    ]


def test_parse_fiche_transition_a_zero_est_absente():
    """La Baule 2022 ne chronomètre pas les transitions : 0 s serait un faux."""
    segments = dict(t2area._parse_fiche(FICHE_TRIATHLON))

    assert segments["Transition 1"] == ""
    assert segments["Natation"] == "00:41:16"


def test_appliquer_splits_triathlon():
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_TRIATHLON))

    assert r.swim_time == "00:41:16"
    assert r.bike_time == "01:14:59"
    assert r.run_time == "00:45:39"
    assert r.t1_time == ""
    assert r.t2_time == ""
    assert r.segments is None


def test_appliquer_splits_duathlon_par_libelle_et_non_par_position():
    """« CàP 1 » va au slot natation, « CàP 2 » au slot course : c'est ce qu'attend
    `_SPLIT_KEYS_BY_SPORT`, qui les ré-étiquette en course1/course2."""
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_DUATHLON))

    assert r.swim_time == "00:22:47"
    assert r.t1_time == "00:01:29"
    assert r.bike_time == "01:24:14"
    assert r.t2_time == "00:02:07"
    assert r.run_time == "00:58:39"


def test_appliquer_splits_duathlon_reetiquete_par_mapping():
    """Bout à bout avec la couche service : les clés finales sont celles du sport."""
    from app.services.mapping import build_splits

    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")
    r.event_type = "duathlon-m"
    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_DUATHLON))

    assert build_splits(r) == {
        "course1": "00:22:47", "t1": "00:01:29", "bike": "01:24:14",
        "t2": "00:02:07", "course2": "00:58:39",
    }


def test_appliquer_splits_libelle_inconnu_bascule_sur_segments():
    """Un seul libellé hors table suffit : rien n'est perdu silencieusement."""
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, t2area._parse_fiche(FICHE_LIBELLE_INCONNU))

    assert r.segments == [("Natation 1", "00:10:00"), ("Trail 1", "00:20:00")]
    assert r.swim_time == ""
    assert r.bike_time == ""


PAGES_LABAULE: dict[str, str | FakeResponse] = {
    "/triathlon-m/2022.html": EDITION_LABAULE,
    "/triathlon-m.html": EPREUVE_LABAULE,
    "/2022/bib-566.html": FICHE_TRIATHLON,
    "/2022/bib-983.html": FICHE_TRIATHLON,
}

_HREF_FICHE_ACCENT = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"
)

# Même édition, avec le href de la colonne Détails d'ACCENT Baptiste altéré :
# la source mélange déjà les deux formes sur la même table (le lien Club est
# relatif), donc un basculement de Détails vers du relatif est plausible.
EDITION_LABAULE_HREF_RELATIF = EDITION_LABAULE.replace(
    _HREF_FICHE_ACCENT,
    "/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html",
)
EDITION_LABAULE_HREF_AUTRE_HOST = EDITION_LABAULE.replace(
    _HREF_FICHE_ACCENT,
    "https://evil.example.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html",
)


def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else dict(PAGES_LABAULE), defaut)
    monkeypatch.setattr(t2area.httpx, "Client", lambda *a, **k: client)
    return client


def test_scrape_event_all_ne_charge_que_les_fiches_tcn(monkeypatch):
    """25 requêtes sur les 901 lignes réelles : le coût est borné par l'effectif du club."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 6
    assert client.calls == [
        URL_EDITION,
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html",
        "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-983.html",
    ]


def test_scrape_event_all_applique_les_splits_aux_seuls_tcn(monkeypatch):
    _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert _par_nom(resultats, "ANTOINE").swim_time == ""


def test_scrape_event_all_tronque_une_url_de_fiche(monkeypatch):
    """Le cas réel du Sheet : le lien pointe une fiche, on importe toute l'édition."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_FICHE)

    assert len(resultats) == 6
    assert client.calls[0] == URL_EDITION


def test_scrape_event_all_source_url_est_lurl_soumise(monkeypatch):
    """`scraped.source_url` = URL **soumise**, pas la forme canonique interne.

    Depuis #156, `mapping.get_or_create_course` retient `scraped.source_url` en
    priorité. Poser l'URL canonique ferait dériver `Course.source_url` d'une URL
    de fiche vers l'édition — `rescrape-db --url <fiche>` chercherait une clé
    qu'aucune course ne porterait. On stocke donc l'URL soumise ; l'idempotence
    tient à la troncature répétée de `_parse_url`, pas à une réécriture de la clé.
    """
    _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_FICHE)

    assert {r.source_url for r in resultats} == {URL_FICHE}


def test_scrape_event_all_url_depreuve_resout_la_derniere_edition(monkeypatch):
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EPREUVE)

    assert client.calls[0] == URL_EPREUVE
    assert client.calls[1] == URL_EDITION
    assert len(resultats) == 6


def test_scrape_event_all_fiche_en_echec_nemporte_pas_lepreuve(monkeypatch, caplog):
    pages = dict(PAGES_LABAULE)
    pages["/2022/bib-983.html"] = FakeResponse("", 500)
    _client_factice(monkeypatch, pages=pages)

    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 6
    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert "bib-983" in caplog.text


def test_scrape_event_all_resout_un_href_de_fiche_relatif(monkeypatch):
    """La colonne Détails est absolue sur les pages sondées, mais si elle bascule
    en relatif (comme le lien Club l'est déjà sur la même table), la fiche doit
    rester joignable via `urljoin`."""
    pages = dict(PAGES_LABAULE)
    pages["/triathlon-m/2022.html"] = EDITION_LABAULE_HREF_RELATIF
    client = _client_factice(monkeypatch, pages=pages)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert _HREF_FICHE_ACCENT in client.calls


def test_scrape_event_all_ignore_un_href_de_fiche_hors_host(monkeypatch):
    """Un href de fiche pointant un autre host est ignoré, sans requête : sinon
    `httpx.UnsupportedProtocol`/une réponse d'un tiers serait rattrapée par
    l'`except httpx.HTTPError` et disparaîtrait dans un simple warning."""
    pages = dict(PAGES_LABAULE)
    pages["/triathlon-m/2022.html"] = EDITION_LABAULE_HREF_AUTRE_HOST
    client = _client_factice(monkeypatch, pages=pages)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert not any("evil.example.com" in call for call in client.calls)
    assert _par_nom(resultats, "ACCENT").swim_time == ""


def test_scrape_event_all_edition_inexistante_leve(monkeypatch):
    """Le site répond 303 vers son accueil : pas de classement vide silencieux."""
    _client_factice(monkeypatch, pages={}, defaut=FakeResponse(
        "<html><body><h1>CALENDRIER DES ÉPREUVES FFTRI</h1></body></html>"
    ))

    with pytest.raises(ValueError, match="Aucun classement"):
        t2area.scrape_event_all(URL_EDITION)


def test_registry_detecte_le_provider():
    from app.scrapers import registry

    assert registry.detect_provider(URL_EDITION) == "t2area"
    assert registry.detect_provider(URL_FICHE) == "t2area"


def test_registry_nattrape_pas_les_autres_sous_domaines_t2area():
    """Allowlist explicite : T2Area sert d'autres fédérations, hors périmètre."""
    from app.scrapers import registry

    assert registry.detect_provider("https://ffn.t2area.com/calendrier/x/y.html") != "t2area"


def test_registry_expose_t2area_comme_ciblable():
    """`provider_names()` alimente la validation de `--provider` en CLI."""
    from app.scrapers import registry

    assert "t2area" in registry.provider_names()
