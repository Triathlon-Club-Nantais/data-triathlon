"""
Tests unitaires pour scrapers/utils.py.

Cas couverts :
- normalize_time : tous les formats d'entrée, valeurs vides/invalides
- normalize_rank : entier, chaîne, None, valeur avec suffixe
- split_athlete_name : convention Wiclax (NOM Prénom), cas limites
"""
import pytest
from scrapers.utils import normalize_time, normalize_rank, split_athlete_name


# ---------------------------------------------------------------------------
# normalize_time
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    # Formats h/m/s
    ("00h39'11",   "00:39:11"),
    ("1h23'45",    "01:23:45"),
    ("01h33'44",   "01:33:44"),
    ("1h23m45s",   "01:23:45"),
    # HH:MM:SS
    ("1:23:45",    "01:23:45"),
    ("01:23:45",   "01:23:45"),
    ("10:05:03",   "10:05:03"),
    # MM:SS (no hours)
    ("39:11",      "00:39:11"),
    ("5:30",       "00:05:30"),
    # h/m sans secondes
    ("1h23",       "01:23:00"),
    ("2h05",       "02:05:00"),
    # Apostrophe typographique
    ("1h23’45", "01:23:45"),
    # Vide
    ("",           ""),
    (None,         ""),
    # Valeur non reconnue → retournée telle quelle
    ("Abandon",    "Abandon"),
    ("DNF",        "DNF"),
    # Zéro
    ("00:00:00",   "00:00:00"),
])
def test_normalize_time(raw, expected):
    assert normalize_time(raw) == expected


# ---------------------------------------------------------------------------
# normalize_rank
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("val,expected", [
    (1,      1),
    ("1",    1),
    ("42",   42),
    ("3e",   3),       # suffixe "e" (3ème)
    ("1st",  1),
    (None,   None),
    ("",     None),
    ("abc",  None),
    ("0",    0),
])
def test_normalize_rank(val, expected):
    assert normalize_rank(val) == expected


# ---------------------------------------------------------------------------
# split_athlete_name
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("full,expected_surname,expected_first", [
    ("DUPONT Jean",          "DUPONT",    "Jean"),
    ("MARTIN Marie-Claire",  "MARTIN",    "Marie-Claire"),
    ("LE BRAS Yann",         "LE BRAS",   "Yann"),       # nom composé
    ("DUDOUYT Clement",      "DUDOUYT",   "Clement"),
    ("dupont jean",          "jean",      "dupont"),      # pas de majuscules → dernier mot = nom (convention Wiclax)
    ("",                     "",          ""),
    ("DUPONT",               "DUPONT",    ""),            # nom seul
])
def test_split_athlete_name(full, expected_surname, expected_first):
    surname, firstname = split_athlete_name(full)
    assert surname == expected_surname
    assert firstname == expected_first
