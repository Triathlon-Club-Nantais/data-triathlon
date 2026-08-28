"""
Tests unitaires pour scrapers/breizhchrono.py (sans réseau).

Couvre le parsing d'URL (deux formats), l'extraction de la date d'épreuve
et l'import d'un heat via le moteur data block partagé (klikego_platform).
"""
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.scrapers import breizhchrono
from app.scrapers.breizhchrono import (
    _parse_bc_date,
    _parse_bc_url,
    _parse_live_heats,
    _parse_live_index,
    _parse_live_slug,
    _parse_live_url,
)
from app.scrapers.klikego_platform import course_name


def test_parse_bc_url_standard():
    """Format /resultats-courses/{slug}-{event-id}/{heat}."""
    url = (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-la-cote-de-granit-rose-tregastel-2026-1295405190290-19/triathlon-m"
    )
    event_id, heat, slug = _parse_bc_url(url)
    assert event_id == "1295405190290-19"
    assert heat == "triathlon-m"
    assert slug == "triathlon-de-la-cote-de-granit-rose-tregastel-2026"


def test_parse_bc_url_no_heat():
    """Sans heat dans le chemin → heat vide."""
    url = (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "triathlon-de-vannes-2025-1234567890123-7"
    )
    event_id, heat, slug = _parse_bc_url(url)
    assert event_id == "1234567890123-7"
    assert heat == ""
    assert slug == "triathlon-de-vannes-2025"


def test_parse_bc_url_coureur_jsp():
    """Format direct-bib coureur.jsp?ref=&heat=&dossard=."""
    url = (
        "https://resultats.breizhchrono.com/bc/resultats/coureur.jsp"
        "?ref=1295405190290-19&heat=triathlon-s&dossard=42"
    )
    event_id, heat, slug = _parse_bc_url(url)
    assert event_id == "1295405190290-19"
    assert heat == "triathlon-s"
    assert slug == ""


def test_parse_bc_date_iso():
    html = '<div><span class="tag">2026-06-07</span></div>'
    assert _parse_bc_date(html) == date(2026, 6, 7)


def test_parse_bc_date_absent():
    assert _parse_bc_date("<div>pas de date ici</div>") is None


def test_parse_bc_date_fr_format():
    """Le front live affiche la date au format FR (DD/MM/YYYY)."""
    assert _parse_bc_date('<span class="event-date">12/09/2025</span>') == date(2025, 9, 12)


def test_parse_bc_date_iso_prime_sur_fr():
    """Si les deux formats sont présents, l'ISO (plus spécifique) l'emporte."""
    html = "<span>2025-09-12</span><span>01/01/2000</span>"
    assert _parse_bc_date(html) == date(2025, 9, 12)


def test_breizhchrono_delegates_to_klikego_platform():
    """Breizh Chrono ne duplique pas la logique de liste :
    _import_one_heat délègue au moteur partagé klikego_platform.build_heat_results.
    Garantit que les statuts DNF/DNS/DSQ sont couverts via le data block.
    """
    import inspect

    from app.scrapers import klikego_platform

    src = inspect.getsource(breizhchrono._import_one_heat)
    assert "build_heat_results" in src
    assert callable(klikego_platform.build_heat_results)


def test_bc_import_one_heat_returns_dnf(monkeypatch):
    """_import_one_heat retourne les DNF/DNS via le data block (moteur partagé)."""
    from pathlib import Path
    page0 = (Path(__file__).parent / "fixtures" / "klikego_datablock_page0.html").read_text()

    class FakeResp:
        def __init__(self, t, code=200): self.text, self.status_code = t, code

    class FakeClient:
        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    results = breizhchrono._import_one_heat(
        "1488071608761-572", "triathlon-s-light", "Triathlon S LIGHT",
        "Triathlon Audencia La Baule 2024", "triathlon-audencia-la-baule-2024",
        date(2024, 9, 28), FakeClient(),
    )
    assert len(results) == 50
    assert any(r.status == "DNF" for r in results)
    assert all(r.provider == "breizhchrono" for r in results)
    assert all(r.is_relay is False for r in results)  # heat non-relais


def test_fetch_all_heats_suit_la_redirection_302():
    """La racine d'événement répond 302 vers un heat (#296).

    `_fetch_all_heats` ne doit pas se contenter du suivi implicite
    (`follow_redirects=True` du client par défaut) : elle lit le 302
    explicitement, refait un GET sur sa cible (`location`), et découvre les
    heats dans le corps de CETTE page — qui embarque la même nav inter-heats
    que la racine aurait portée. Reproduit la mesure faite sur Mesquer 2026.
    """
    heat_page = """
    <html><body>
      <a href="/resultats-courses/tri-mesquer-42/swim-run-m-duo">Swim Run M Duo</a>
      <a href="/resultats-courses/tri-mesquer-42/swim-run-s-indiv">Swim Run S Indiv</a>
      <a href="/resultats-courses/tri-mesquer-42/swim-run-s-duo">Swim Run S Duo</a>
      <a href="/resultats-courses/tri-mesquer-42/swim-run-m-duo/export">export</a>
    </body></html>
    """

    class _RedirectResp:
        status_code = 302
        is_redirect = True
        headers = {"location": "/resultats-courses/tri-mesquer-42/swim-run-m-duo"}
        text = ""

    class _HeatResp:
        status_code = 200
        is_redirect = False
        headers: dict = {}
        text = heat_page

    demandes: list[tuple[str, bool]] = []

    class _Client:
        def get(self, url, follow_redirects=True):
            demandes.append((url, follow_redirects))
            if follow_redirects is False:
                return _RedirectResp()
            return _HeatResp()

    heats = breizhchrono._fetch_all_heats("tri-mesquer-42", _Client())

    assert demandes[0] == (
        "https://resultats.breizhchrono.com/resultats-courses/tri-mesquer-42",
        False,
    )
    assert demandes[1][0] == (
        "https://resultats.breizhchrono.com/resultats-courses/"
        "tri-mesquer-42/swim-run-m-duo"
    )
    assert heats == [
        ("swim-run-m-duo", "Swim Run M Duo"),
        ("swim-run-s-indiv", "Swim Run S Indiv"),
        ("swim-run-s-duo", "Swim Run S Duo"),
    ]


def test_fetch_all_heats_redirection_vers_ip_interne_refusee(monkeypatch):
    """Le suivi explicite du 302 ne doit pas contourner le garde SSRF (#101).

    Traiter la redirection comme un signal plutôt que la suivre en silence ne
    doit pas rouvrir la voie fermée par #101 : la cible reste vérifiée par le
    même garde que n'importe quel autre appel — un client réel (transport
    `MockTransport`), pas un FakeClient, pour engager le vrai `_GuardTransport`.
    """
    from app.core import http
    from app.core.exceptions import BlockedTargetError

    monkeypatch.setattr(http, "_resolve", lambda host, port: ["93.184.216.34"])

    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        if request.url.path == "/resultats-courses/evt-1":
            return httpx.Response(
                302, headers={"Location": "http://169.254.169.254/interne"}
            )
        return httpx.Response(200, text="ne doit jamais être atteint")

    with http.client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(BlockedTargetError):
            breizhchrono._fetch_all_heats("evt-1", client)

    # La cible interne n'a jamais été jointe : le refus part AVANT la requête.
    assert vues == ["https://resultats.breizhchrono.com/resultats-courses/evt-1"]


def test_fetch_all_heats_sans_redirection_reste_couvert():
    """Repli : si la racine répond 200 directement, le parsing d'origine tient."""

    class _Resp:
        status_code = 200
        is_redirect = False
        headers: dict = {}
        text = (
            '<a href="/resultats-courses/evt-1/triathlon-m">Triathlon M</a>'
        )

    class _Client:
        def get(self, url, follow_redirects=True):
            return _Resp()

    heats = breizhchrono._fetch_all_heats("evt-1", _Client())
    assert heats == [("triathlon-m", "Triathlon M")]


def test_fetch_all_heats_exclut_le_classement_durable():
    """Un heat `classement-durable---...` reclasse le MÊME peloton par empreinte
    carbone : ce n'est pas un heat sportif distinct (#703). Non filtré, il
    s'importait comme une épreuve à part entière avec des « finishers »
    fantômes — double comptage des athlètes de la vraie épreuve triathlon
    (mesuré à Trégastel 2026 : 352 finishers fantômes, épreuve id 840).
    """

    class _Resp:
        status_code = 200
        is_redirect = False
        headers: dict = {}
        text = (
            '<a href="/resultats-courses/evt-1/triathlon-m">Triathlon M</a>'
            '<a href="/resultats-courses/evt-1/classement-durable---triathlon">'
            "Classement durable - Triathlon</a>"
        )

    class _Client:
        def get(self, url, follow_redirects=True):
            return _Resp()

    heats = breizhchrono._fetch_all_heats("evt-1", _Client())
    assert heats == [("triathlon-m", "Triathlon M")]


def test_fetch_all_heats_exclut_les_classements_generaux_et_challenges():
    """Autres heats non-sportifs connus sur cette plateforme : le classement
    général toutes épreuves confondues, et les challenges par équipe/club.
    Mêmes pelotons re-classés selon un autre critère, jamais un heat sportif.
    """

    class _Resp:
        status_code = 200
        is_redirect = False
        headers: dict = {}
        text = (
            '<a href="/resultats-courses/evt-1/triathlon-m">Triathlon M</a>'
            '<a href="/resultats-courses/evt-1/classement-general">Classement général</a>'
            '<a href="/resultats-courses/evt-1/challenge-entreprises">Challenge Entreprises</a>'
            '<a href="/resultats-courses/evt-1/general-jeunes">Général Jeunes</a>'
        )

    class _Client:
        def get(self, url, follow_redirects=True):
            return _Resp()

    heats = breizhchrono._fetch_all_heats("evt-1", _Client())
    assert heats == [("triathlon-m", "Triathlon M")]


# --------------------------------------------------------------------------- #
# _detect_relay — libellé et slug (#295)
# --------------------------------------------------------------------------- #


def test_detect_relay_on_a_duo_heat_without_label():
    """Heat ciblé directement : pas de libellé, le slug seul porte le signal.

    `swim-run-m-duo` (Mesquer 2026) sortait `is_relay=False` faute de connaître
    « duo », et un duo compté individuel mélange équipes et solos au classement.
    """
    assert breizhchrono._detect_relay("", "swim-run-m-duo") is True


def test_detect_relay_on_a_duo_label():
    """Le libellé affiché suffit quand il porte le format (« Swim Run M Duo »)."""
    assert breizhchrono._detect_relay("Swim Run M Duo", "swim-run-m") is True


def test_detect_relay_keeps_individual_heats_solo():
    """Un heat individuel reste solo, quel que soit le côté d'où on le regarde."""
    assert breizhchrono._detect_relay("Swim Run S Indiv", "swim-run-s-indiv") is False
    assert breizhchrono._detect_relay("", "swimrun-court-solo") is False


def test_detect_relay_still_reads_the_truncated_relay_slug():
    """Non-régression : un slug relais tronqué à « --- » reste détecté.

    Sur Breizh Chrono, le slug d'un heat relais dont le libellé manque se
    termine par « --- » ; ce signal-là ne passe par aucun mot.
    """
    assert breizhchrono._detect_relay("", "triathlon-m---") is True


# --------------------------------------------------------------------------- #
# Front live.breizhchrono.com (moteur Klikego, façade différente) — issue #34
# --------------------------------------------------------------------------- #

_LIVE_CLASSEMENTS = (
    Path(__file__).parent / "fixtures" / "breizhchrono_live_classements.html"
).read_text()

_LIVE_INDEX = (
    Path(__file__).parent / "fixtures" / "breizhchrono_live_index.html"
).read_text()


def test_parse_live_url_avec_heat():
    url = (
        "https://live.breizhchrono.com/external/live5/classements.jsp"
        "?version=new&reference=1488071608761-688&heat=triathlon-distance-olympique"
    )
    reference, heat = _parse_live_url(url)
    assert reference == "1488071608761-688"
    assert heat == "triathlon-distance-olympique"


def test_parse_live_url_sans_heat():
    """index.jsp?reference= → reference seule, heat vide (import de toute l'épreuve)."""
    url = "https://live.breizhchrono.com/external/live5/index.jsp?reference=1488071608761-688"
    reference, heat = _parse_live_url(url)
    assert reference == "1488071608761-688"
    assert heat == ""


def test_parse_live_heats_dedoublonne():
    """Les heats sont les liens classements.jsp?...&heat= ; les doublons sautent."""
    heats = _parse_live_heats(_LIVE_CLASSEMENTS)
    slugs = [s for s, _ in heats]
    assert slugs == [
        "triathlon-distance-olympique",
        "swimrun-court-solo",
        "triathlon-distance-olympique---relais",
        "trail-11-km",
    ]
    # Le libellé permet la détection de relais en aval.
    labels = dict(heats)
    assert "Relais" in labels["triathlon-distance-olympique---relais"]


def test_parse_live_slug():
    """Le slug se lit dans le lien d'export de classements.jsp."""
    assert _parse_live_slug(_LIVE_CLASSEMENTS) == "triathlon-swimrun-dinard-cote-demeraude-2025"


def test_classements_ne_porte_aucune_date():
    """Garde-fou : classements.jsp n'expose PAS de date (c'est index.jsp qui l'a).

    Une date fictive dans la fixture avait masqué le bug « courses sans date ».
    """
    assert _parse_bc_date(_LIVE_CLASSEMENTS) is None


def test_parse_live_index_nom_et_dates_par_heat():
    """index.jsp donne le vrai nom d'épreuve (accentué) et une date PAR heat."""
    event_name, dates = _parse_live_index(_LIVE_INDEX)
    assert event_name == "Triathlon SwimRun Dinard Côte d'Emeraude"
    # Les heats d'une même épreuve peuvent tomber des jours différents.
    assert dates["trail 11 km"] == date(2025, 9, 12)
    assert dates["triathlon distance olympique"] == date(2025, 9, 14)
    assert dates["swimrun court solo"] == date(2025, 9, 14)


def test_parse_live_index_vide():
    """HTML inexploitable → pas de nom, pas de dates (aucune exception)."""
    assert _parse_live_index("<html></html>") == ("", {})


def test_bc_utilise_le_course_name_partage_avec_klikego():
    """`course_name` vit désormais dans `klikego_platform` (partagée avec Klikego,
    #308) : Breizh Chrono ne porte plus sa propre implémentation. Les cas de
    composition eux-mêmes sont couverts par test_klikego.py."""
    import inspect

    src = inspect.getsource(breizhchrono._import_one_heat)
    assert "course_name(event_name, heat_label)" in src
    assert (
        course_name("Triathlon SwimRun Dinard Côte d'Emeraude", "Trail 11 KM")
        == "Triathlon SwimRun Dinard Côte d'Emeraude - Trail 11 KM"
    )


def test_live_import_one_heat_route_sur_lhote_live(monkeypatch):
    """_import_one_heat(base=LIVE_BASE, event_type=…) décode course-result.jsp
    sur l'hôte live et honore le type d'épreuve fourni (classification heat-seul).
    """
    page0 = (
        Path(__file__).parent / "fixtures" / "klikego_datablock_page0.html"
    ).read_text()

    calls = {"urls": []}

    class FakeResp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    class FakeClient:
        def get(self, url):
            calls["urls"].append(url)
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            return FakeResp("<html></html>")

    results = breizhchrono._import_one_heat(
        "1488071608761-688", "triathlon-distance-olympique", "Triathlon Distance Olympique",
        "Triathlon Swimrun Dinard Cote Demeraude 2025",
        "triathlon-swimrun-dinard-cote-demeraude-2025",
        date(2025, 9, 12), FakeClient(),
        base=breizhchrono.LIVE_BASE,
        source_url="https://live.breizhchrono.com/external/live5/classements.jsp"
        "?version=new&reference=1488071608761-688&heat=triathlon-distance-olympique",
        event_type="triathlon-m",
    )
    assert len(results) == 50
    # Le décodage a bien tapé l'hôte live (course-result.jsp sur live.breizhchrono.com).
    assert any(
        "live.breizhchrono.com/bc/resultats/course-result.jsp" in u
        for u in calls["urls"]
    )
    # Le type fourni prime (le slug « swimrun » n'a PAS pollué la classification).
    assert all(r.event_type == "triathlon-m" for r in results)
    assert all(r.provider == "breizhchrono" for r in results)


def test_registry_route_live_vers_moteur_klikego(monkeypatch):
    """L'URL live.breizhchrono.com n'est plus rejetée : elle route vers
    scrape_live_event_all avec (reference, heat) extraits de l'URL."""
    from app.scrapers import registry

    captured = {}

    def fake_live(reference, heat=""):
        captured["reference"] = reference
        captured["heat"] = heat
        return ["sentinel"]

    monkeypatch.setattr(breizhchrono, "scrape_live_event_all", fake_live)

    url = (
        "https://live.breizhchrono.com/external/live5/index.jsp"
        "?reference=1488071608761-688"
    )
    assert registry.detect_provider(url) == "breizhchrono"
    out = registry.scrape_event_all(url)
    assert out == ["sentinel"]
    assert captured == {"reference": "1488071608761-688", "heat": ""}


def test_registry_route_live_insensible_casse(monkeypatch):
    """Un hôte en majuscules (URL copiée/collée) route quand même vers le live."""
    from app.scrapers import registry

    captured = {}

    def fake_live(reference, heat=""):
        captured["reference"] = reference
        return ["sentinel"]

    monkeypatch.setattr(breizhchrono, "scrape_live_event_all", fake_live)

    url = "https://LIVE.BreizhChrono.com/external/live5/index.jsp?reference=42-7"
    assert registry.scrape_event_all(url) == ["sentinel"]
    assert captured["reference"] == "42-7"


def test_registry_ne_route_pas_un_host_prefixe_vers_le_live(monkeypatch):
    """`live.breizhchrono.com.evil.tld` satisfaisait le `in` du dispatch (#432).

    L'égalité stricte sur le host le renvoie à la façade classique, donc à
    aucune requête vers un hôte contrôlé par un tiers via le moteur live.
    """
    from app.scrapers.registry import BreizhChronoProvider

    def refuse_live(*a, **kw):
        raise AssertionError("routé vers le moteur live sur un host usurpé")

    monkeypatch.setattr(breizhchrono, "scrape_live_event_all", refuse_live)
    monkeypatch.setattr(breizhchrono, "scrape_event_all", lambda *a, **kw: ["classique"])

    url = (
        "https://live.breizhchrono.com.evil.tld/external/live5/index.jsp"
        "?reference=1488071608761-688"
    )
    assert BreizhChronoProvider().scrape_event_all(url) == ["classique"]


def test_live_mode_heat_unique_conserve_le_libelle_pour_le_relais(monkeypatch):
    """En mode heat unique, le libellé est récupéré depuis classements.jsp afin
    que la détection de relais fonctionne pour un slug live « ...---relais »."""
    page0 = (
        Path(__file__).parent / "fixtures" / "klikego_datablock_page0.html"
    ).read_text()

    class FakeResp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url):
            if "course-result.jsp" in url and "inter=&page=0" in url:
                return FakeResp(page0)
            if "course-result.jsp" in url:
                return FakeResp("<html></html>")
            # Page racine classements.jsp (sans heat=) → liste des heats + libellés.
            if "classements.jsp" in url and "heat=" not in url:
                return FakeResp(_LIVE_CLASSEMENTS)
            return FakeResp("<html></html>")

    monkeypatch.setattr(breizhchrono.httpx, "Client", lambda *a, **k: FakeClient())

    results = breizhchrono.scrape_live_event_all(
        "1488071608761-688", "triathlon-distance-olympique---relais"
    )
    assert len(results) == 50
    # Le libellé « ... - Relais » du root a bien été récupéré → is_relay propagé.
    assert all(r.is_relay is True for r in results)


class _FakeLiveClient:
    """Client live factice : sert classements.jsp, index.jsp et le data block."""

    def __init__(self):
        self.page0 = (
            Path(__file__).parent / "fixtures" / "klikego_datablock_page0.html"
        ).read_text()

    class _Resp:
        def __init__(self, t, code=200):
            self.text, self.status_code = t, code

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url):
        if "course-result.jsp" in url and "inter=&page=0" in url:
            return self._Resp(self.page0)
        if "index.jsp" in url:
            return self._Resp(_LIVE_INDEX)
        if "classements.jsp" in url and "heat=" not in url:
            return self._Resp(_LIVE_CLASSEMENTS)
        return self._Resp("<html></html>")


def test_live_chaque_heat_a_son_nom_et_sa_date(monkeypatch):
    """Régression : les heats d'une épreuve live ne partagent plus un nom unique
    ni une date absente.

    Avant : les 4 heats sortaient tous nommés « Triathlon Swimrun Dinard Cote
    Demeraude 2025 » avec event_date=None → le Trail s'affichait sous un nom de
    triathlon, et les heats de même type fusionnaient sur l'identité de course.
    """
    monkeypatch.setattr(breizhchrono.httpx, "Client", lambda *a, **k: _FakeLiveClient())

    results = breizhchrono.scrape_live_event_all("1488071608761-688")

    by_name = {r.event_name: r for r in results}
    assert set(by_name) == {
        "Triathlon SwimRun Dinard Côte d'Emeraude - Triathlon Distance Olympique",
        "Triathlon SwimRun Dinard Côte d'Emeraude - Swimrun Court Solo",
        "Triathlon SwimRun Dinard Côte d'Emeraude - Triathlon Distance Olympique - Relais",
        "Triathlon SwimRun Dinard Côte d'Emeraude - Trail 11 KM",
    }
    # Date propre à chaque heat (le trail court la veille des triathlons).
    trail = by_name["Triathlon SwimRun Dinard Côte d'Emeraude - Trail 11 KM"]
    olympique = by_name[
        "Triathlon SwimRun Dinard Côte d'Emeraude - Triathlon Distance Olympique"
    ]
    assert trail.event_date == date(2025, 9, 12)
    assert olympique.event_date == date(2025, 9, 14)
    # Le type reste classé sur le heat seul.
    assert trail.event_type == "trail"
    assert olympique.event_type == "triathlon-m"


def test_bc_classique_nomme_chaque_heat():
    """Même correctif côté resultats.breizhchrono.com : un heat = une course nommée."""
    results = breizhchrono._import_one_heat(
        "1488071608761-688", "trail-11-km", "Trail 11 KM",
        "Triathlon Swimrun Dinard Cote Demeraude 2025",
        "triathlon-swimrun-dinard-cote-demeraude-2025",
        date(2025, 9, 12), _FakeLiveClient(),
    )
    assert results
    assert all(
        r.event_name == "Triathlon Swimrun Dinard Cote Demeraude 2025 - Trail 11 KM"
        for r in results
    )


def test_les_splits_fins_ne_sont_cherches_que_pour_le_club(monkeypatch):
    """Un club nantais qui n'est pas le nôtre ne déclenche plus de requête (#76)."""
    import httpx

    from app.scrapers import breizhchrono
    from app.scrapers.base import ScrapedResult

    demandes: list[str] = []

    class _Client:
        def get(self, url: str):
            demandes.append(url)
            return httpx.Response(404, request=httpx.Request("GET", url))

    # `source_url` et `provider` sont les deux champs sans valeur par défaut.
    def _resultat(club: str, bib: str) -> ScrapedResult:
        return ScrapedResult(
            source_url="https://live.breizhchrono.com/evt",
            provider="breizhchrono",
            club=club,
            bib_number=bib,
        )

    results = [
        _resultat("TRI CLUB NANTAIS", "1"),
        _resultat("RACING CLUB NANTAIS *", "2"),
        _resultat("ASPTT RENNES", "3"),
    ]

    breizhchrono._fetch_tcn_fine_splits(
        "https://live.breizhchrono.com", "evt", "heat", results, _Client()
    )

    assert len(demandes) == 1
    assert "dossard=1" in demandes[0]


def test_une_date_d_epreuve_injoignable_est_journalisee(monkeypatch, caplog):
    """Un échec sur la page de date ne doit pas être avalé en silence.

    `event_date = None` change la clé `UNIQUE(name, event_date, event_type)` de
    `Course` : sans trace, une épreuve importée sans date est indiscernable
    d'une épreuve qui n'en publie pas.
    """
    class _Resp:
        text, status_code = "<html></html>", 200

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, follow_redirects=True):
            # Seule la page racine — celle qui porte la date — est injoignable.
            if url.endswith("/resultats-courses/tri-test-42"):
                raise httpx.ConnectError("breizhchrono injoignable")
            return _Resp()

    monkeypatch.setattr(breizhchrono.http, "client", lambda **k: _Client())

    with caplog.at_level("WARNING"):
        results = breizhchrono.scrape_event_all("42", "", "Triathlon de Test", "tri-test")

    assert results == []
    assert "breizhchrono injoignable" in caplog.text
