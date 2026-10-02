"""
Tests unitaires pour scrapers/t2area.py (sans réseau).

Les fixtures d'édition et de fiche sont des extraits réels de fftri.t2area.com,
re-sondés le 30/09/2026 après le changement de markup (#898) : une carte
`article.edition-result` par participant, splits compris, et une fiche réduite à
son bandeau de rangs et à ses `div.rd-split`. La page d'épreuve date du
26/07/2026 : seuls ses liens d'édition y sont lus, et ils n'ont pas changé.
"""
import logging
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

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

URL_EDITION = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022.html"
)
URL_FICHE = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"
)
URL_EPREUVE = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m.html"
URL_EVENEMENT = "https://fftri.t2area.com/calendrier/triathlon-de-la-baule.html"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200, url: str = ""):
        self.text, self.status_code, self.url = text, status_code, url

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


def test_parse_edition_lit_une_carte_par_participant():
    assert len(_labaule()) == 9


def test_parse_edition_champs_dun_finisher():
    r = _par_nom(_labaule(), "ACCENT")

    assert (r.athlete_name, r.athlete_firstname) == ("ACCENT", "Baptiste")
    assert r.club == "TRIATHLON CLUB NANTAIS"
    assert r.category == "MS2"
    assert r.gender == "M"
    assert r.rank_overall == 453
    assert r.total_time == "02:41:52"
    assert r.bib_number == "566"
    assert r.status == ""          # finisher : laissé à l'heuristique de mapping
    assert r.is_relay is False
    assert r.provider == "t2area"
    assert r.source_url == URL_EDITION


def test_parse_edition_la_liste_ne_publie_plus_les_rangs_genre_et_categorie():
    """#898 : ils ne vivent plus que sur la fiche, chargée pour les membres TCN."""
    r = _par_nom(_labaule(), "ANTOINE")

    assert r.gender == "F"
    assert r.rank_gender is None
    assert r.rank_category is None


def test_parse_edition_entete_lu_dans_le_title():
    """Le `<h1>` ne dit plus que « Édition 2022 » : le nom et la date viennent du
    `<title>`, et la date entre dans l'identité de la Course."""
    r = _labaule()[0]

    assert r.event_name == "Triathlon de La Baule - M"
    assert r.event_date == date(2022, 9, 18)
    assert r.event_type == "triathlon-m"


def test_parse_edition_splits_de_tous_les_participants():
    """Les splits sont sur la liste, pour tout le monde ; « — » vaut absent (La
    Baule 2022 ne chronomètre pas les transitions)."""
    r = _par_nom(_labaule(), "ANTOINE")

    assert (r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time) == (
        "00:40:51", "", "01:23:15", "", "00:56:51",
    )
    assert r.segments is None


def test_parse_edition_finisher_sans_fiche_ni_splits():
    """Huit finishers de La Baule n'ont ni lien de fiche ni splits : pas de dossard."""
    r = _par_nom(_labaule(), "GROSBOIS")

    assert r.rank_overall == 58
    assert r.bib_number == ""
    assert r.swim_time == ""


def test_parse_edition_dnf():
    r = _par_nom(_labaule(), "EPP")

    assert r.status == "DNF"
    assert r.total_time == ""
    assert r.rank_overall is None
    assert r.swim_time == "00:28:07"


def test_parse_edition_disqualifie_navance_ni_temps_ni_rang():
    """La FFTRI publie parfois un temps sur un DSQ (`42:23:00`, ALLARD Pierre) :
    invariant du dépôt, un non-finisher n'a pas de temps total. Le brut reste
    diagnosticable dans `raw_data`."""
    r = _par_nom(_labaule(), "ALLARD")

    assert r.status == "DSQ"
    assert r.total_time == ""
    assert r.rank_overall is None
    assert r.raw_data["temps"] == "42:23:00"


def test_parse_edition_club_absent():
    assert _par_nom(_labaule(), "AGIS").club == ""


def test_parse_edition_ligne_anonyme_du_site():
    """« 907 Dossard » : une entrée sans identité, telle que la source la publie.

    Aucune heuristique locale — le scraper ne devine pas d'identité. Son badge
    « --- » ne vaut pas catégorie.
    """
    r = _par_nom(_labaule(), "Dossard")

    assert (r.athlete_name, r.athlete_firstname) == ("Dossard", "907")
    assert r.bib_number == "907"
    assert r.category == ""


def test_parse_edition_raw_data_conserve_le_contexte():
    r = _par_nom(_labaule(), "ACCENT")

    assert r.raw_data["cle_fiche"] == "bib-566"
    assert r.raw_data["league"] == "PAYS DE LA LOIRE"
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
    r = _par_nom(resultats, "FEUGIER")

    assert r.bib_number == ""
    assert r.raw_data["cle_fiche"] == "A15993"
    assert r.event_name == "Triathlon du Lac du Bouchet (43) - L"
    assert r.event_date == date(2025, 7, 13)
    assert r.event_type == "triathlon-l"
    assert r.t2_time == "00:01:38"


def _nevers() -> list:
    return t2area._parse_edition(
        EDITION_NEVERS,
        "https://fftri.t2area.com/calendrier/triathlon-de-nevers/duathlon-m/2022.html",
        "triathlon-de-nevers",
        "duathlon-m",
    )


def test_parse_edition_duathlon_range_les_cap_par_libelle():
    """« CàP 1 » va au slot natation, « CàP 2 » au slot course : c'est ce qu'attend
    `SPLIT_KEYS_BY_SPORT`, qui les ré-étiquette en course1/course2."""
    r = _par_nom(_nevers(), "BOURGEOIS")

    assert r.event_type == "duathlon-m"
    assert (r.swim_time, r.t1_time, r.bike_time, r.t2_time, r.run_time) == (
        "00:17:25", "00:00:54", "00:59:19", "00:01:18", "00:36:22",
    )


def test_parse_edition_duathlon_reetiquete_par_mapping():
    """Bout à bout avec la couche service : les clés finales sont celles du sport."""
    from app.services.mapping import build_splits

    assert build_splits(_par_nom(_nevers(), "BOURGEOIS")) == {
        "course1": "00:17:25", "t1": "00:00:54", "bike": "00:59:19",
        "t2": "00:01:18", "course2": "00:36:22",
    }


def test_parse_edition_genre_lu_sans_badge_de_categorie():
    """SKLADZIEN Victor n'a pas de badge : le genre vient de `data-gender`."""
    r = _par_nom(_nevers(), "SKLADZIEN")

    assert r.category == ""
    assert r.gender == "M"


def test_parse_edition_sans_carte_leve():
    """Markup changé : mieux vaut une erreur qu'un classement vide importé."""
    with pytest.raises(ValueError, match="markup fftri modifié"):
        t2area._parse_edition(
            "<html><head><title>Résultats du X - M - 2022 - édition du 18-09-2022</title>"
            "</head><body><table id=\"resultList\"></table></body></html>",
            URL_EDITION,
            "triathlon-de-la-baule",
            "triathlon-m",
        )


def test_fetch_edition_repere_la_redirection_vers_le_calendrier():
    """Édition inexistante : 303 vers `/calendrier.html`, donc 200 après la
    redirection. Le message ne doit pas accuser le markup (#898)."""
    client = FakeClient(defaut=FakeResponse(
        "<html><body>calendrier</body></html>", url="https://fftri.t2area.com/calendrier.html"
    ))

    with pytest.raises(t2area.EditionIntrouvableError, match="Édition inexistante"):
        t2area._fetch_edition(client, URL_EDITION)


def test_libelle_de_split_inconnu_bascule_sur_segments():
    """Un seul libellé hors table suffit : rien n'est perdu silencieusement."""
    r = ScrapedResult(source_url=URL_EDITION, provider="t2area")

    t2area._appliquer_splits(r, [("Natation 1", "00:10:00"), ("Trail 1", "00:20:00")])

    assert r.segments == [("Natation 1", "00:10:00"), ("Trail 1", "00:20:00")]
    assert r.swim_time == ""
    assert r.bike_time == ""


@pytest.mark.parametrize("brut,attendu", [
    ("02:41:52", "02:41:52"),
    ("00:00:00", ""),      # DNF : temps absent, pas un temps nul
    ("—", ""),             # split non chronométré sur la liste
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
    ("swimrun-s-binome", True),     # mots d'équipe partagés (#963)
    ("triathlon-m-team", True),
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
        "<html><head><title>Résultats — édition du 18-09-2022</title></head></html>", "lxml"
    )
    nom, event_date = t2area._entete(soup, "triathlon-de-la-baule", "triathlon-m")

    assert event_date == date(2022, 9, 18)
    assert nom == "Triathlon De La Baule Triathlon M"


# Mention réelle de Vichy L 2024 : un chronométreur que nous savons lire.
EDITION_RACERESULT = EDITION_LABAULE.replace("http://www.ipitos.com/", "http://my3.raceresult.com/")


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


def test_parse_fiche_lit_les_rangs_sexe_et_categorie():
    """Bandeau réel d'ACCENT Baptiste : « 453 Global », « 419 Sexe », « 89 Catégorie »."""
    assert t2area._parse_fiche(FICHE_TRIATHLON) == {"rank_gender": 419, "rank_category": 89}
    assert t2area._parse_fiche(FICHE_DUATHLON) == {"rank_gender": 1, "rank_category": 1}


def test_parse_fiche_sans_bandeau():
    assert t2area._parse_fiche("<html><body></body></html>") == {}


PAGES_LABAULE: dict[str, str | FakeResponse] = {
    "/triathlon-m/2022.html": EDITION_LABAULE,
    "/triathlon-m.html": EPREUVE_LABAULE,
    "/2022/bib-566.html": FICHE_TRIATHLON,
}

_HREF_FICHE_ACCENT = (
    "https://fftri.t2area.com/calendrier/triathlon-de-la-baule/triathlon-m/2022/bib-566.html"
)

# Même édition, avec le lien de fiche d'ACCENT Baptiste altéré : la carte mélange
# déjà liens absolus (fiche) et relatifs (club, athlète).
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


def test_scrape_event_all_ne_charge_que_les_fiches_des_finishers_tcn(monkeypatch):
    """25 requêtes sur les 901 lignes réelles : borné par l'effectif du club. EPP
    Arnaud (TCN, DNF) n'a aucun rang à lire : sa fiche n'est pas chargée."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 9
    assert client.calls == [URL_EDITION, _HREF_FICHE_ACCENT]


def test_scrape_event_all_pose_les_rangs_de_la_fiche_aux_seuls_tcn(monkeypatch):
    _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_EDITION)

    accent = _par_nom(resultats, "ACCENT")
    assert (accent.rank_gender, accent.rank_category) == (419, 89)
    assert _par_nom(resultats, "ANTOINE").rank_gender is None


def test_scrape_event_all_tronque_une_url_de_fiche(monkeypatch):
    """Le cas réel du Sheet : le lien pointe une fiche, on importe toute l'édition."""
    client = _client_factice(monkeypatch)

    resultats = t2area.scrape_event_all(URL_FICHE)

    assert len(resultats) == 9
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
    assert len(resultats) == 9


def test_scrape_event_all_fiche_en_echec_nemporte_pas_lepreuve(monkeypatch, caplog):
    pages = dict(PAGES_LABAULE)
    pages["/2022/bib-566.html"] = FakeResponse("", 500)
    _client_factice(monkeypatch, pages=pages)

    with caplog.at_level(logging.WARNING, logger="app.scrapers.t2area"):
        resultats = t2area.scrape_event_all(URL_EDITION)

    assert len(resultats) == 9
    assert _par_nom(resultats, "ACCENT").rank_gender is None
    assert _par_nom(resultats, "ACCENT").swim_time == "00:41:16"
    assert "bib-566" in caplog.text


def test_scrape_event_all_resout_un_href_de_fiche_relatif(monkeypatch):
    pages = dict(PAGES_LABAULE)
    pages["/triathlon-m/2022.html"] = EDITION_LABAULE_HREF_RELATIF
    client = _client_factice(monkeypatch, pages=pages)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert _par_nom(resultats, "ACCENT").rank_gender == 419
    assert _HREF_FICHE_ACCENT in client.calls


def test_scrape_event_all_ignore_un_href_de_fiche_hors_host(monkeypatch):
    """Un href de fiche pointant un autre host est ignoré, sans requête : sinon
    `httpx.UnsupportedProtocol`/une réponse d'un tiers serait rattrapée par
    l'`except httpx.HTTPError` et disparaîtrait dans un simple warning."""
    pages = dict(PAGES_LABAULE)
    pages["/triathlon-m/2022.html"] = EDITION_LABAULE_HREF_AUTRE_HOST
    client = _client_factice(monkeypatch, pages=pages)

    resultats = t2area.scrape_event_all(URL_EDITION)

    assert all(urlsplit(call).hostname == "fftri.t2area.com" for call in client.calls)
    assert _par_nom(resultats, "ACCENT").rank_gender is None


def test_scrape_event_all_edition_inexistante_leve(monkeypatch):
    """Le site répond 303 vers son calendrier : pas de classement vide silencieux."""
    _client_factice(monkeypatch, pages={}, defaut=FakeResponse(
        "<html><body>calendrier</body></html>", url="https://fftri.t2area.com/calendrier.html"
    ))

    with pytest.raises(ValueError, match="Édition inexistante"):
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
