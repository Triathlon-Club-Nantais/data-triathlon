"""
Tests unitaires pour scrapers/breizhchrono.py (sans réseau).

Couvre le parsing d'URL (deux formats), l'extraction de la date d'épreuve
et l'import d'un heat via le moteur data block partagé (klikego_platform).
"""
from datetime import date

from app.scrapers import breizhchrono
from app.scrapers.breizhchrono import _parse_bc_date, _parse_bc_url


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
