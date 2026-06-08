"""
Tests unitaires pour scrapers/breizhchrono.py (sans réseau).

Couvre le parsing d'URL (deux formats) et l'extraction de la date d'épreuve.
Le parsing des résultats lui-même est partagé avec klikego (testé dans
test_klikego.py via _parse_detail / _parse_search_row).
"""
from datetime import date

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
