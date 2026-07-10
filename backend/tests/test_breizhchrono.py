"""
Tests unitaires pour scrapers/breizhchrono.py (sans réseau).

Couvre le parsing d'URL (deux formats), l'extraction de la date d'épreuve
et l'import d'un heat via le moteur data block partagé (klikego_platform).
"""
from datetime import date
from pathlib import Path

from app.scrapers import breizhchrono
from app.scrapers.breizhchrono import (
    _parse_bc_date,
    _parse_bc_url,
    _parse_live_heats,
    _parse_live_meta,
    _parse_live_url,
)


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


# --------------------------------------------------------------------------- #
# Front live.breizhchrono.com (moteur Klikego, façade différente) — issue #34
# --------------------------------------------------------------------------- #

_LIVE_CLASSEMENTS = (
    Path(__file__).parent / "fixtures" / "breizhchrono_live_classements.html"
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
    ]
    # Le libellé permet la détection de relais en aval.
    labels = dict(heats)
    assert "Relais" in labels["triathlon-distance-olympique---relais"]


def test_parse_live_meta():
    """slug lu dans le lien d'export, date au format FR."""
    slug, event_date = _parse_live_meta(_LIVE_CLASSEMENTS)
    assert slug == "triathlon-swimrun-dinard-cote-demeraude-2025"
    assert event_date == date(2025, 9, 12)


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
