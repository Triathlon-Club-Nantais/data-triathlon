"""Tests unitaires pour le helper de reconnaissance de statut (sans réseau)."""
from datetime import date

import pytest

from app.scrapers.utils import derive_status_from_label, parse_fr_date, split_athlete_name


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
    # Formes plurielles des groupes RaceResult
    ("Abandons", "DNF"),
    ("Non Partants", "DNS"),
])
def test_derive_status_from_label_recognized(label, expected):
    assert derive_status_from_label(label) == expected


@pytest.mark.parametrize("label", ["", "   ", "12e", "SEH", "blah", "01:23:45"])
def test_derive_status_from_label_unknown_returns_empty(label):
    assert derive_status_from_label(label) == ""


@pytest.mark.parametrize("text,expected", [
    # Mois en toutes lettres (comportement existant)
    ("16 mai 2026", date(2026, 5, 16)),
    ("16 septembre 2024", date(2024, 9, 16)),
    ("16–17 mai 2026", date(2026, 5, 16)),
    # Mois abrégés Klikego (avec point final)
    ("12 avr. 2026", date(2026, 4, 12)),
    ("1 janv. 2026", date(2026, 1, 1)),
    ("3 févr. 2026", date(2026, 2, 3)),
    ("28 sept. 2024", date(2024, 9, 28)),
    ("5 juil. 2025", date(2025, 7, 5)),
    ("24 déc. 2025", date(2025, 12, 24)),
    ("9 nov. 2025", date(2025, 11, 9)),
    ("2 oct. 2025", date(2025, 10, 2)),
    # Abrégés sans point (tolérance)
    ("12 avr 2026", date(2026, 4, 12)),
])
def test_parse_fr_date_ok(text, expected):
    assert parse_fr_date(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "pas de date", "32 avr. 2026"])
def test_parse_fr_date_none(text):
    assert parse_fr_date(text) is None


@pytest.mark.parametrize("brut,attendu", [
    # Convention RaceResult « Prénom NOM » — le nom est le bloc majuscule final.
    ("Alexis ROUX", ("ROUX", "Alexis")),
    ("Jean DE LA TOUR", ("DE LA TOUR", "Jean")),
    ("Marie-Claire LE GALL", ("LE GALL", "Marie-Claire")),
    # Convention Wiclax/TimePulse « NOM Prénom » — comportement inchangé.
    ("ROUX Alexis", ("ROUX", "Alexis")),
    ("LE GALL Marie-Claire", ("LE GALL", "Marie-Claire")),
    # Aucun bloc majuscule : repli sur le dernier token (comportement inchangé).
    ("Jean Dupont", ("Dupont", "Jean")),
    # Cas dégénérés.
    ("", ("", "")),
    ("MARTIN", ("MARTIN", "")),
    # Limite assumée : prénom entièrement en majuscules bascule à tort sur « NOM Prénom ».
    ("JP ROUX", ("JP ROUX", "")),
    ("JEAN MARTIN", ("JEAN MARTIN", "")),
])
def test_split_athlete_name(brut, attendu):
    assert split_athlete_name(brut) == attendu
