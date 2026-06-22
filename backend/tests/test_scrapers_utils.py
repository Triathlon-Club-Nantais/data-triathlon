"""Tests unitaires pour le helper de reconnaissance de statut (sans réseau)."""
import pytest

from app.scrapers.utils import derive_status_from_label


@pytest.mark.parametrize("label,expected", [
    # Disqualification (FR/EN, casse/ponctuation/accents)
    ("DSQ", "DSQ"),
    ("Disqualifié", "DSQ"),
    ("disqualified", "DSQ"),
    ("Disq.", "DSQ"),
    # Abandon
    ("DNF", "DNF"),
    ("Abandon", "DNF"),
    ("ABD", "DNF"),
    ("Ab.", "DNF"),
    # Non-partant
    ("DNS", "DNS"),
    ("Non partant", "DNS"),
    ("NON PARTANT", "DNS"),
    ("Forfait", "DNS"),
    ("NP", "DNS"),
    # Finisher (label positif explicite)
    ("Finisher", "finisher"),
    ("Classé", "finisher"),
])
def test_derive_status_from_label_recognized(label, expected):
    assert derive_status_from_label(label) == expected


@pytest.mark.parametrize("label", ["", "   ", "12e", "SEH", "blah", "01:23:45"])
def test_derive_status_from_label_unknown_returns_empty(label):
    assert derive_status_from_label(label) == ""
