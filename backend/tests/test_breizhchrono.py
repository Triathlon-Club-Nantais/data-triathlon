"""
Tests unitaires pour scrapers/breizhchrono.py.

Cas couverts :
- _parse_bc_url : formats standard, coureur.jsp, URL sans heat
- event_type depuis le heat slug (via klikego._detect_event_type)
- Détection du sport depuis le heat (pas depuis le slug — évite les faux positifs)
"""
import pytest
from scrapers.breizhchrono import _parse_bc_url
from scrapers.klikego import _detect_event_type


# ---------------------------------------------------------------------------
# _parse_bc_url
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("url,expected_id,expected_heat,expected_slug", [
    # Format standard avec heat
    (
        "https://resultats.breizhchrono.com/resultats-courses/triathlon-s-dinard-2025-1385456266352-13/sprint-solo",
        "1385456266352-13", "sprint-solo", "triathlon-s-dinard-2025",
    ),
    # Format avec heat composé
    (
        "https://resultats.breizhchrono.com/resultats-courses/duathlon-bardon-saint-gregoire-2025-1385456266352-13/d2-hommes",
        "1385456266352-13", "d2-hommes", "duathlon-bardon-saint-gregoire-2025",
    ),
    # Sans heat (page racine de l'événement)
    (
        "https://resultats.breizhchrono.com/resultats-courses/triathlon-rennes-2025-1385456266352-99",
        "1385456266352-99", "", "triathlon-rennes-2025",
    ),
    # Format coureur.jsp
    (
        "https://resultats.breizhchrono.com/bc/resultats/coureur.jsp?ref=1385456266352-13&heat=sprint-solo&dossard=42",
        "1385456266352-13", "sprint-solo", "",
    ),
])
def test_parse_bc_url(url, expected_id, expected_heat, expected_slug):
    event_id, heat, slug = _parse_bc_url(url)
    assert event_id == expected_id
    assert heat == expected_heat
    assert slug == expected_slug


# ---------------------------------------------------------------------------
# Détection event_type depuis le heat slug (pas le slug événement)
# _detect_event_type est partagé entre klikego et breizhchrono
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("heat,slug,expected", [
    # Triathlon
    ("triathlon-s",            "triathlon-s",            "triathlon-s"),
    ("triathlon-s-individuel", "triathlon-s-individuel", "triathlon-s"),
    ("triathlon-m",            "triathlon-m",            "triathlon-m"),
    ("triathlon-l",            "triathlon-l",            "triathlon-l"),
    ("triathlon-xl",           "triathlon-xl",           "triathlon-xl"),
    ("sprint-solo",            "sprint-solo",            "triathlon-s"),
    # Duathlon — le suffix doit avoir "-" après "s" pour être reconnu "duathlon-s"
    ("duathlon-s-individuel",  "duathlon-s-individuel",  "duathlon-s"),
    ("duathlon-m-individuel",  "duathlon-m-individuel",  "duathlon-m"),
    ("duathlon-s",             "duathlon-s",             "duathlon"),   # pas de suffix "-" → fallback
    # "d2-hommes" ne contient pas "duathlon" → triathlon fallback
    ("d2-hommes",              "d2-hommes",              "triathlon"),
    # SwimRun — "court" → swimrun-s, "long" → swimrun-l
    ("swimrun-classique",      "swimrun-classique",      "swimrun"),
    ("swimrun-s-solo",         "swimrun-s-solo",         "swimrun"),    # "format-s"/"court" absent
    ("swimrun-court-solo",     "swimrun-court-solo",     "swimrun-s"),  # "court" présent
    # Aquathlon
    ("aquathlon-individuel",   "aquathlon-individuel",   "aquathlon"),
])
def test_event_type_from_heat(heat, slug, expected):
    assert _detect_event_type(heat, slug) == expected


def test_heat_takes_priority_over_slug():
    """
    Régression — quand le slug contenait "triathlon" ET "swimrun" (ex: triathlon-swimrun-dinard),
    le scraper donnait triathlon-s. Avec le heat "swimrun-court-solo", doit donner swimrun-s.
    """
    assert _detect_event_type("swimrun-court-solo", "triathlon-swimrun-dinard") == "swimrun-s"
