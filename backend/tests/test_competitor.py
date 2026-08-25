"""
Tests du scraper Competitor / WTC (ironman.com, issue #54).

Fixtures : extraits réels du 2026-07-26 — page « Results » d'ironman.com
(3 iframes), page Next.js de la série IRONMAN France, et deux réponses du proxy
OData. Aucun réseau : `httpx.Client` est remplacé par un client factice
(pattern `test_chronoplace.py`).
"""
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import competitor, registry
from app.scrapers.base import STATUS_DNF, STATUS_DNS, STATUS_DSQ, STATUS_FINISHER

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(nom: str) -> str:
    return (FIXTURES / nom).read_text(encoding="utf-8")


PAGE_IRONMAN = _fixture("competitor_ironman_results.html")
SERIE = _fixture("competitor_serie_im_france.html")
RESULTS_2025 = _fixture("competitor_results_2025.json")
RESULTS_2025_P1 = _fixture("competitor_results_2025_page1.json")
RESULTS_2025_P2 = _fixture("competitor_results_2025_page2.json")
RESULTS_2024 = _fixture("competitor_results_2024.json")

URL_IRONMAN = "https://www.ironman.com/races/im-france/results"
SERIE_UUID = "bb98aa20-f278-e111-b16a-005056956277"
EDITION_2025 = "f3a6cf4c-e9d5-4c6f-a425-86b3b8ba0524"
EDITION_2024 = "66511861-b71e-44fd-8c65-cd282323354c"


class FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text, self.status_code = text, status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return json.loads(self.text)


class FakeClient:
    """Client HTTP factice : sert les fixtures et enregistre les URLs demandées."""

    def __init__(self, pages=None, defaut=None):
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


# Ordre significatif : `FakeClient` retient le premier motif contenu dans l'URL.
# L'uuid d'édition 2024 apparaît dans deux URLs (la page de série et la requête
# proxy), la route de page doit donc être testée avant lui.
PAGES = {
    "ironman.com": PAGE_IRONMAN,
    f"/results/event/{SERIE_UUID}": SERIE,
    f"/results/event/{EDITION_2024}": SERIE,
    EDITION_2025: RESULTS_2025,
    EDITION_2024: RESULTS_2024,
}


def _client_factice(monkeypatch, pages=None, defaut=None):
    client = FakeClient(pages if pages is not None else dict(PAGES), defaut)
    monkeypatch.setattr(competitor.httpx, "Client", lambda *a, **k: client)
    return client


# ── Résolution de l'URL ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        f"https://labs-v2.competitor.com/results/event/{SERIE_UUID}",
        f"https://labs-v2.competitor.com/results/event/odiv/{SERIE_UUID}",
        f"https://labs-v2.competitor.com/results/event/{SERIE_UUID.upper()}",
    ],
)
def test_uuid_lu_directement_dans_lurl_competitor(url):
    assert competitor._uuid_depuis_url(url) == SERIE_UUID


def test_uuid_absent_dune_url_ironman():
    """Une page ironman.com ne porte pas l'uuid : il faudra la télécharger."""
    assert competitor._uuid_depuis_url(URL_IRONMAN) is None


def test_uuid_resolu_depuis_liframe_de_classement(monkeypatch):
    client = _client_factice(monkeypatch)
    assert competitor._resoudre_uuid(client, URL_IRONMAN) == SERIE_UUID


def test_liframe_odiv_et_clubpoints_ne_sont_pas_prises():
    """La page porte 3 iframes ; seule celle du classement doit matcher."""
    assert PAGE_IRONMAN.count("labs-v2.competitor.com") == 3
    assert competitor._RE_IFRAME.search("labs-v2.competitor.com/clubpoints/event/x") is None
    assert (
        competitor._RE_IFRAME.search(
            f"labs-v2.competitor.com/results/event/odiv/{SERIE_UUID}"
        )
        is None
    )


def test_page_sans_iframe_est_rejetee(monkeypatch):
    client = _client_factice(monkeypatch, {"ironman.com": "<html>rien</html>"})
    with pytest.raises(ValueError, match="Aucune iframe de résultats"):
        competitor._resoudre_uuid(client, URL_IRONMAN)


# ── Lecture de __NEXT_DATA__ et choix de l'édition ───────────────────────────


def test_uuid_inconnu_rejete_malgre_un_200(monkeypatch):
    """La source rend 200 + pageProps vide sur un uuid inconnu, pas un 404."""
    vide = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"pageProps":{}}}</script></html>'
    )
    client = _client_factice(monkeypatch, {"/results/event/": vide})
    with pytest.raises(ValueError, match="introuvable"):
        competitor._fetch_next_data(client, SERIE_UUID)


def test_page_sans_next_data_est_rejetee(monkeypatch):
    client = _client_factice(monkeypatch, {"/results/event/": "<html>vide</html>"})
    with pytest.raises(ValueError, match="__NEXT_DATA__"):
        competitor._fetch_next_data(client, SERIE_UUID)


def test_uuid_de_serie_selectionne_la_derniere_edition(monkeypatch):
    client = _client_factice(monkeypatch)
    props = competitor._fetch_next_data(client, SERIE_UUID)
    edition = competitor._choisir_edition(props, SERIE_UUID)
    assert edition["wtc_eventid"] == EDITION_2025
    assert edition["wtc_name"] == "2025 IRONMAN France Nice"


def test_uuid_dedition_selectionne_cette_edition(monkeypatch):
    """L'adressabilité par année que le site n'offre pas."""
    client = _client_factice(monkeypatch)
    props = competitor._fetch_next_data(client, SERIE_UUID)
    edition = competitor._choisir_edition(props, EDITION_2024)
    assert edition["wtc_name"] == "2024 IRONMAN France Nice"


def test_date_dedition_lue_en_iso():
    assert competitor._date_edition({"wtc_eventdate": "2025-06-29T00:00:00Z"}) == date(
        2025, 6, 29
    )


def test_date_dedition_repli_sur_la_forme_americaine():
    assert competitor._date_edition(
        {"wtc_eventdate": "", "wtc_eventdate_formatted": "6/29/2025"}
    ) == date(2025, 6, 29)


def test_date_dedition_absente_ne_leve_pas():
    assert competitor._date_edition({}) is None


# ── Import complet — édition courante ────────────────────────────────────────


def test_import_edition_courante(monkeypatch):
    client = _client_factice(monkeypatch)
    resultats = competitor.scrape_event_all(URL_IRONMAN)

    assert len(resultats) == 4
    # 1 GET ironman.com + 1 GET la page de série + 1 requête de classement.
    assert len(client.calls) == 3


def test_latest_results_de_la_page_est_ignore(monkeypatch):
    """Le rendu serveur ampute l'Open Division : on redemande le classement.

    Mesuré sur IRONMAN France 2025 : `latestResults` porte 1748 lignes quand la
    requête sans filtre en rend 1810 — 62 athlètes ODIV passés à la trappe.
    """
    client = _client_factice(monkeypatch)
    resultats = competitor.scrape_event_all(URL_IRONMAN)

    assert [appel for appel in client.calls if "results-proxy" in appel]
    # La fixture de page ne contient pas d'ODIV ; le classement redemandé, si.
    assert "ODIV" not in SERIE
    assert [r for r in resultats if r.category == "ODIV"]


def test_champs_dun_finisher(monkeypatch):
    _client_factice(monkeypatch)
    finisher = competitor.scrape_event_all(URL_IRONMAN)[0]

    assert finisher.provider == "competitor"
    assert finisher.source_url == URL_IRONMAN
    assert (finisher.athlete_name, finisher.athlete_firstname) == ("Terrier", "Vincent")
    assert finisher.bib_number == "3544"
    assert finisher.category == "M30-34"
    assert finisher.event_name == "2025 IRONMAN France Nice"
    assert finisher.event_date == date(2025, 6, 29)
    assert finisher.event_type == "triathlon-xl"
    assert finisher.status == STATUS_FINISHER
    assert finisher.total_time == "08:59:34"
    assert finisher.rank_overall == 1
    assert finisher.rank_category == 1
    assert finisher.rank_gender == 1
    assert finisher.is_relay is False


def test_splits_dans_les_cinq_slots(monkeypatch):
    _client_factice(monkeypatch)
    finisher = competitor.scrape_event_all(URL_IRONMAN)[0]

    # T1 = `wtc_transition1timeformatted`, T2 = `wtc_transitiontime2formatted` :
    # l'asymétrie de nommage de la source ne doit pas se voir ici.
    assert finisher.swim_time == "00:51:48"
    assert finisher.t1_time == "00:03:47"
    assert finisher.bike_time == "04:59:44"
    assert finisher.t2_time == "00:03:50"
    assert finisher.run_time == "03:00:25"


def test_genre_lu_sur_la_categorie_pas_sur_le_contact(monkeypatch):
    """`wtc_ContactId.gendercode` dit « Female » pour ce vainqueur masculin."""
    _client_factice(monkeypatch)
    finisher = competitor.scrape_event_all(URL_IRONMAN)[0]

    assert finisher.raw_data["wtc_ContactId"]["gendercode_formatted"] == "Female"
    assert finisher.gender == "M"


def test_non_finisher_perd_temps_et_rangs_mais_garde_ses_splits(monkeypatch):
    _client_factice(monkeypatch)
    dnf = competitor.scrape_event_all(URL_IRONMAN)[1]

    assert dnf.status == STATUS_DNF
    assert dnf.total_time == ""
    assert (dnf.rank_overall, dnf.rank_category, dnf.rank_gender) == (None, None, None)
    # Le nageur a bien nagé : le split partiel est une donnée réelle.
    assert dnf.swim_time == "01:19:16"
    assert dnf.bike_time == ""
    # `0:00:00` est une absence, pas un temps.
    assert dnf.raw_data["wtc_transitiontime2formatted"] == "0:00:00"
    assert dnf.t2_time == ""


def test_dns_reconnu(monkeypatch):
    _client_factice(monkeypatch)
    dns = competitor.scrape_event_all(URL_IRONMAN)[2]
    assert dns.status == STATUS_DNS
    assert dns.total_time == ""


def test_statut_lu_sur_les_quatre_drapeaux_dans_lordre():
    """`wtc_dq` prime, et n'apparaît sur **aucune** ligne du panel sondé (0 /
    1585) : seul un test unitaire peut couvrir la disqualification."""
    assert competitor._statut({"wtc_dq": True}) == STATUS_DSQ
    assert competitor._statut({"wtc_dq": True, "wtc_finisher": True}) == STATUS_DSQ
    assert competitor._statut({"wtc_dns": True}) == STATUS_DNS
    assert competitor._statut({"wtc_dnf": True}) == STATUS_DNF
    assert competitor._statut({"wtc_finisher": True}) == STATUS_FINISHER
    # Mesuré : 3 lignes sur 1585 (Vichy 2024) n'ont aucun des quatre drapeaux.
    assert competitor._statut({}) == ""


def test_disqualifie_perd_temps_et_rangs():
    """Un DSQ suit le même traitement qu'un DNF, drapeau non observé compris."""
    dsq = competitor._build_result(
        {
            "wtc_dq": True,
            "wtc_finishtimeformatted": "9:12:00",
            "wtc_finishrankoverall": 12,
            "wtc_swimtimeformatted": "1:02:11",
        },
        url=URL_IRONMAN,
        event_name="2025 IRONMAN France Nice",
        event_date=date(2025, 6, 29),
        event_type="triathlon-xl",
    )

    assert dsq.status == STATUS_DSQ
    assert dsq.total_time == ""
    assert dsq.rank_overall is None
    # Le nageur a bien nagé, ici aussi.
    assert dsq.swim_time == "01:02:11"


def test_aucun_club_publie_par_la_source(monkeypatch):
    """La source n'a pas de champ club : le rattachement TCN est impossible ici."""
    _client_factice(monkeypatch)
    resultats = competitor.scrape_event_all(URL_IRONMAN)
    assert all(r.club == "" for r in resultats)


def test_rang_sentinelle_99999_devient_none():
    assert competitor._rang(99999) is None
    assert competitor._rang("99999") is None
    assert competitor._rang(None) is None
    assert competitor._rang(12) == 12


def test_temps_sentinelle_devient_vide():
    assert competitor._temps("0:00:00") == ""
    assert competitor._temps(None) == ""
    assert competitor._temps("8:59:34") == "08:59:34"


def test_dossard_replie_sur_bibnumber_v2():
    assert competitor._dossard({"wtc_bibnumber": None, "wtc_bibnumber_v2": "A12"}) == "A12"
    assert competitor._dossard({}) == ""


# ── Pagination et édition ancienne (via le proxy) ────────────────────────────


def test_pagination_suivie_via_le_proxy(monkeypatch):
    """Deux pages OData recollées ; le nextLink est suivi tel quel."""
    appels: list[str] = []

    class ClientPagine(FakeClient):
        def get(self, url: str):
            if "results-proxy" in url:
                appels.append(url)
                corps = RESULTS_2025_P1 if len(appels) == 1 else RESULTS_2025_P2
                return FakeResponse(corps)
            return super().get(url)

    client = ClientPagine(dict(PAGES))
    monkeypatch.setattr(competitor.httpx, "Client", lambda *a, **k: client)

    resultats = competitor.scrape_event_all(URL_IRONMAN)

    assert len(resultats) == 4  # 2 + 2
    assert len(appels) == 2
    # Le front réécrit `/web/wtc_results?` en `/web/results?` : on fait pareil.
    assert "web%2Fresults" in appels[1]
    assert "wtc_results" not in appels[1]


def test_pagination_bornee_puis_en_echec(monkeypatch):
    """Un nextLink qui boucle borne l'import — et le fait échouer, pas tronquer.

    Rendre les pages déjà lues figerait un classement incomplet dans le cache
    30 jours ; l'échec, lui, est rejouable (`rescrape-db --url`).
    """
    boucle = json.dumps(
        {
            "value": json.loads(RESULTS_2025)["value"][:1],
            "@odata.nextLink": "https://api.competitor.com/web/results?$skiptoken=boucle",
        }
    )
    # `results-proxy` en tête : toutes les pages de classement bouclent.
    client = _client_factice(monkeypatch, {"results-proxy": boucle, **PAGES})

    with pytest.raises(ValueError, match="Pagination Competitor interrompue"):
        competitor.scrape_event_all(URL_IRONMAN)

    appels = [appel for appel in client.calls if "results-proxy" in appel]
    assert len(appels) == competitor._MAX_PAGES


def test_edition_ancienne_interrogee_via_le_proxy(monkeypatch):
    client = _client_factice(monkeypatch)
    url = f"https://labs-v2.competitor.com/results/event/{EDITION_2024}"

    resultats = competitor.scrape_event_all(url)

    appels = [appel for appel in client.calls if "results-proxy" in appel]
    assert len(appels) == 1
    assert EDITION_2024 in appels[0].lower().replace("%20", " ")
    assert resultats[0].event_name == "2024 IRONMAN France Nice"
    assert resultats[0].event_date == date(2024, 6, 16)
    # Les pages du proxy n'ont pas les champs de confort du rendu serveur.
    assert "athlete" not in resultats[0].raw_data
    assert resultats[0].athlete_name


def test_open_division_importee_sans_rang(monkeypatch):
    """L'ODIV est exclue du classement officiel mais reste des participants."""
    _client_factice(monkeypatch)
    resultats = competitor.scrape_event_all(URL_IRONMAN)

    odiv = [r for r in resultats if r.category == "ODIV"]
    assert len(odiv) == 1
    assert odiv[0].athlete_name == "Bierry"
    assert odiv[0].status == STATUS_FINISHER
    assert odiv[0].total_time == "13:23:32"
    # Non classé à la source (sentinelle 99999), et ça reste vrai chez nous.
    assert odiv[0].rank_overall is None


def test_doublons_de_pagination_ecartes(monkeypatch):
    """Une ligne réapparue d'une page à l'autre ne crée pas de doublon."""
    appels: list[str] = []
    page1 = json.loads(RESULTS_2025_P1)

    class ClientPagine(FakeClient):
        def get(self, url: str):
            if "results-proxy" in url:
                appels.append(url)
                if len(appels) == 1:
                    return FakeResponse(RESULTS_2025_P1)
                # La page 2 resert la première ligne de la page 1.
                return FakeResponse(json.dumps({"value": [page1["value"][0]]}))
            return super().get(url)

    client = ClientPagine(dict(PAGES))
    monkeypatch.setattr(competitor.httpx, "Client", lambda *a, **k: client)

    assert len(competitor.scrape_event_all(URL_IRONMAN)) == 2


def test_edition_sans_identifiant_est_rejetee(monkeypatch):
    """Sans uuid d'édition, le `$filter` OData partirait vide : 400 illisible."""
    serie = (
        '<html><script id="__NEXT_DATA__" type="application/json">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {"subevents": [{"wtc_name": "2025 IRONMAN France Nice"}]}
                }
            }
        )
        + "</script></html>"
    )
    _client_factice(
        monkeypatch, {"ironman.com": PAGE_IRONMAN, "/results/event/": serie}
    )

    with pytest.raises(ValueError, match="sans identifiant"):
        competitor.scrape_event_all(URL_IRONMAN)


def test_epreuve_sans_resultat_est_rejetee(monkeypatch):
    pages = dict(PAGES)
    pages[EDITION_2025] = json.dumps({"value": []})
    _client_factice(monkeypatch, pages)

    with pytest.raises(ValueError, match="aucun résultat publié"):
        competitor.scrape_event_all(URL_IRONMAN)


def test_client_httpx_suit_les_redirections(monkeypatch):
    vus: dict = {}

    def espion(*args, **kwargs):
        vus.update(kwargs)
        return FakeClient(dict(PAGES))

    monkeypatch.setattr(competitor.httpx, "Client", espion)
    competitor.scrape_event_all(URL_IRONMAN)

    assert vus.get("follow_redirects") is True
    assert vus.get("timeout") == 30


# ── Registre ─────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://www.ironman.com/races/im-france/results",
        "https://ironman.com/im-france-results",
        f"https://labs-v2.competitor.com/results/event/{SERIE_UUID}",
        "https://www.ironman.com:443/races/im-vichy/results",
    ],
)
def test_registry_detecte_le_provider(url):
    assert registry.detect_provider(url) == "competitor"


@pytest.mark.parametrize(
    "url",
    [
        "https://ironman.com.attaquant.net/races/x/results",
        "https://eviltroncompetitor.com/results/event/x",
        "https://www.klikego.com/resultats/x/1",
    ],
)
def test_registry_nattrape_pas_les_hosts_sosies(url):
    assert registry.detect_provider(url) != "competitor"


def test_registry_expose_competitor_comme_ciblable():
    assert "competitor" in registry.provider_names()
