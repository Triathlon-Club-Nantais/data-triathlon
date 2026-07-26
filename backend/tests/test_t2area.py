"""
Tests unitaires pour scrapers/t2area.py (sans réseau).

Les fixtures sont des extraits réels de fftri.t2area.com (2026-07-26), réduits à
quelques lignes ; les attributs purement décoratifs ont été retirés, la structure
(`#resultList`, en-tête à 10 colonnes, accordéon des fiches) est intacte.
"""
from pathlib import Path

import httpx
import pytest

from app.scrapers import t2area

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


EPREUVE_LABAULE = _fixture("t2area_epreuve_labaule_m.html")

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

    def __init__(self, pages: dict[str, str] | None = None, defaut: FakeResponse | None = None):
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
