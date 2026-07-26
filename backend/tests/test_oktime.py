"""
Tests unitaires pour scrapers/oktime.py (sans réseau).

Les fixtures sont des charges API réduites, calquées sur le schéma mesuré au
panel du 2026-07-26 (cf. docs/superpowers/specs/2026-07-26-oktime-scraper-design.md).
Le schéma réel est revérifié par le test `integration` sur l'événement 48555.
"""
import json
from pathlib import Path

import httpx
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


FIXTURES = Path(__file__).parent / "fixtures"

PAGE_EVENEMENT = (FIXTURES / "oktime_evenement_page.html").read_text(encoding="utf-8")


class FakeResponse:
    """Réponse HTTP factice, texte + JSON."""

    def __init__(self, contenu, status_code: int = 200):
        self.status_code = status_code
        if isinstance(contenu, str):
            self.text, self._json = contenu, None
        else:
            self.text, self._json = json.dumps(contenu), contenu

    def json(self):
        if self._json is None:
            raise ValueError("réponse non-JSON")
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class FakeClient:
    """Client HTTP factice : sert les réponses et enregistre les URLs demandées."""

    def __init__(self, pages: dict | None = None, defaut: FakeResponse | None = None):
        self.pages = pages or {}
        self.defaut = defaut or FakeResponse("<html>404</html>", 404)
        self.calls: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url: str):
        self.calls.append(url)
        for motif, reponse in self.pages.items():
            if motif in url:
                return reponse if isinstance(reponse, FakeResponse) else FakeResponse(reponse)
        return self.defaut


def test_resolve_event_id_lit_le_lien_de_classement():
    client = FakeClient({"/evenement/": PAGE_EVENEMENT})

    assert oktime._resolve_event_id(client, "triathlon-de-lacanau-2026") == "48555"
    assert client.calls == ["https://ok-time.fr/evenement/triathlon-de-lacanau-2026/"]


def test_resolve_event_id_sans_lien_leve():
    """Page 200 mais sans lien de classement : la forme `/course/triathlon-l/`
    redirigée vers le listing générique n'a aucun id à offrir."""
    client = FakeClient({"/evenement/": "<html><body>Aucun classement.</body></html>"})

    with pytest.raises(ValueError, match="aucun lien de classement"):
        oktime._resolve_event_id(client, "triathlon-l")


def test_fetch_results_rend_la_charge():
    charge = {"success": True, "evenement_id": 48555, "count": 0, "data": []}
    client = FakeClient({"/wp-json/gmcap/v1/evenements/48555/results": charge})

    assert oktime._fetch_results(client, "48555") == charge
    assert client.calls == [
        "https://ok-time.fr/wp-json/gmcap/v1/evenements/48555/results"
    ]


def test_fetch_results_404_id_inconnu():
    client = FakeClient(
        defaut=FakeResponse({"message": "Ce post n'est pas un evenement."}, 404)
    )

    with pytest.raises(ValueError, match="introuvable"):
        oktime._fetch_results(client, "1")


def test_fetch_results_400_sans_resultats_publies():
    """Événement réel mais sans fichier de résultats : cause distincte du 404."""
    client = FakeClient(
        defaut=FakeResponse(
            {"message": "Aucun fichier_gmcap défini pour cet evenement."}, 400
        )
    )

    with pytest.raises(ValueError, match="aucun résultat publié"):
        oktime._fetch_results(client, "48555")


def test_fetch_results_500_remonte_en_erreur_http():
    """Une panne serveur n'est pas une erreur métier : elle ne doit pas être
    traduite en ValueError, qui la ferait passer pour un lien invalide."""
    client = FakeClient(defaut=FakeResponse("boom", 500))

    with pytest.raises(httpx.HTTPError):
        oktime._fetch_results(client, "48555")


def test_fetch_results_charge_sans_data_leve():
    client = FakeClient({"/results": {"success": False}})

    with pytest.raises(ValueError, match="Charge ok-time inattendue"):
        oktime._fetch_results(client, "48555")
