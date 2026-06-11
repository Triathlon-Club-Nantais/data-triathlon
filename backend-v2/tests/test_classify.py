"""Tests du classifieur unique de disciplines (source de vérité)."""
import pytest

from app.scrapers.classify import (
    classify_event_type,
    extract_distance_km,
    normalize_event_type,
)


# --- Triathlon (porté de klikego/timepulse/wiclax, non-régression) ---
@pytest.mark.parametrize("text,expected", [
    ("triathlon-s", "triathlon-s"),
    ("triathlon-s-individuel", "triathlon-s"),
    ("format-s-en-individuel", "triathlon-s"),
    ("triathlon-m---individuel", "triathlon-m"),
    ("triathlon-l", "triathlon-l"),
    ("triathlon-xl", "triathlon-xl"),
    ("medoc-atlantique-frenchman-xxl", "triathlon-xl"),
    ("triathlon-xs-jeunes", "triathlon-s"),            # XS triathlon → S (collapse)
    ("Triathlon de Noirmoutier Sprint 2025", "triathlon-s"),
    ("Triathlon Olympique de Paris 2025", "triathlon-m"),
    ("Triathlon L de Bordeaux", "triathlon-l"),
    ("Ironman France 2025", "triathlon-xl"),
    ("Triathlon XXL Embrunman", "triathlon-xl"),
    ("Triathlon 70.3 Aix-en-Provence", "triathlon-l"),
    ("Triathlon de Lacanau 2025", "triathlon"),
    ("Sprint de la Roche", "triathlon-s"),             # pas de sport explicite → triathlon + taille
    ("triathlon-xl frenchman-2026", "triathlon-xl"),   # heat+slug séparés par espace (régression seg())
    ("triathlon-m nantais-2026", "triathlon-m"),
    ("triathlon-s nantais-sprint-2026", "triathlon-s"),
    ("", "triathlon"),
])
def test_classify_triathlon(text, expected):
    assert classify_event_type(text) == expected


# --- Duathlon ---
@pytest.mark.parametrize("text,expected", [
    ("duathlon-classique", "duathlon"),
    ("duathlon-s-individuel", "duathlon-s"),
    ("duathlon-liffre-cormier-open--xs-court", "duathlon-xs"),
    ("duathlon-liffre-cormier-open--sprint-court", "duathlon-s"),
    ("duathlon-m-individuel", "duathlon-m"),
    ("duathlon-l-individuel", "duathlon-l"),
    ("duathlon-liffre-cormier-clm-par-equipe", "duathlon"),   # "clm" ne doit PAS → cyclisme
    ("Duathlon de Rennes", "duathlon"),
    ("Duathlon Sprint de Couëron 2025", "duathlon-s"),
])
def test_classify_duathlon(text, expected):
    assert classify_event_type(text) == expected


# --- Autres multisports ---
@pytest.mark.parametrize("text,expected", [
    ("swimrun-classique", "swimrun"),
    ("format-s---en-binome re-swimrun-2025", "swimrun-s"),
    ("format-m---en-solo swimrun-cote-beaute-2025", "swimrun-m"),
    ("format-l---championnat re-swimrun-2025", "swimrun-l"),
    ("SwimRun des Îles", "swimrun"),
    ("aquathlon-s-champnat aquathlon-des-2-amants", "aquathlon"),
    ("Aquathlon du RC Doué", "aquathlon"),
    ("Planète Racing Aquarun 2026", "aquarun"),
    ("bikerun-sprint", "bike-run"),
    ("BIKE & RUN d'Halloween", "bike-run"),
    ("Run & Bike du Bignon", "bike-run"),
])
def test_classify_multisport(text, expected):
    assert classify_event_type(text) == expected


# --- Nouveaux mono-sports ---
@pytest.mark.parametrize("text,expected", [
    ("Trail des Forts 23 km", "trail"),
    ("Trail du Mont Blanc L", "trail"),                # ne doit PAS → triathlon-l
    ("Marathon de Nantes 2025", "course-a-pied-marathon"),
    ("Semi-Marathon de Vannes", "course-a-pied-semi"),
    ("Les 10 km de Carquefou", "course-a-pied-10k"),
    ("Foulées du 5 km", "course-a-pied-5k"),
    ("Course sur route de Rezé", "course-a-pied"),
    ("Cyclosportive des Vignes 120 km", "cyclisme-route"),
    ("Cyclisme contre-la-montre", "cyclisme-clm"),
    ("CLM par équipe cyclisme", "cyclisme-clm"),
    ("Cyclisme route 90 km", "cyclisme-route"),
    ("Cyclo de printemps", "cyclisme"),
])
def test_classify_mono_sport(text, expected):
    assert classify_event_type(text) == expected


# --- Normalisation (idempotence + reprise de l'existant) ---
@pytest.mark.parametrize("value,expected", [
    ("Triathlon M", "triathlon-m"),
    ("triathlon-m", "triathlon-m"),       # déjà propre → inchangé
    ("triathlon-l", "triathlon-l"),
    ("duathlon-xs", "duathlon-xs"),
    ("bike-run", "bike-run"),
    ("aquathlon", "aquathlon"),
    ("trail", "trail"),
    ("course-a-pied", "course-a-pied"),         # slug nu : ne doit PAS tomber en triathlon
    ("course-a-pied-10k", "course-a-pied-10k"), # slug avec suffixe
    ("cyclisme-clm", "cyclisme-clm"),            # slug spécialisé cyclisme
    ("aquarun", "aquarun"),                      # slug mono-mot
])
def test_normalize_idempotent(value, expected):
    assert normalize_event_type(value) == expected
    # idempotence stricte : normaliser deux fois = normaliser une fois
    assert normalize_event_type(normalize_event_type(value)) == expected


def test_bike_run_pas_de_faux_positif():
    # "bike" et "run" comme sous-chaînes de mots distincts ne doivent PAS
    # déclencher bike-run (frontières de mots requises).
    assert classify_event_type("Bikepark Runner Cup") != "bike-run"
    # mais les vraies formes restent reconnues
    assert classify_event_type("Run & Bike du Bignon") == "bike-run"
    assert classify_event_type("bikerun-sprint") == "bike-run"


# --- Extraction du kilométrage ---
@pytest.mark.parametrize("text,expected", [
    ("Trail des Forts 23 km", 23.0),
    ("Cyclo 120km", 120.0),
    ("Trail 42,2 km", 42.2),
    ("Marathon 42.195 km", 42.195),
    ("Triathlon M", None),
    ("", None),
])
def test_extract_distance_km(text, expected):
    assert extract_distance_km(text) == expected
