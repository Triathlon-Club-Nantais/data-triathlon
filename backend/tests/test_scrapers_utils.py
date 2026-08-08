"""Tests unitaires pour le helper de reconnaissance de statut (sans réseau)."""
from datetime import date

import pytest

from app.scrapers.utils import (
    derive_status_from_label,
    fmt_seconds,
    parse_fr_date,
    split_athlete_name,
    to_seconds,
)


@pytest.mark.parametrize("label,expected", [
    # Disqualification (FR/EN, casse/ponctuation/accents)
    ("DSQ", "DSQ"),
    ("Disqualifié", "DSQ"),
    ("disqualified", "DSQ"),
    ("Disq.", "DSQ"),
    # `DQ` : forme employée par fftri.t2area.com dans la colonne Clt (#51).
    ("DQ", "DSQ"),
    ("dq", "DSQ"),
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


# ── to_seconds / fmt_seconds ─────────────────────────────────────────────────
# Définition unique des six copies qu'en portaient klikego, timepulse, wiclax,
# chronoweb, oktime et stats_service (audit de sur-ingénierie, entrée n° 4).


@pytest.mark.parametrize(
    ("brut", "attendu"),
    [
        ("01:23:45", 5025),
        ("00:00:00", 0),
        ("23:45", 1425),      # MM:SS — ce dont `stats_service` a besoin
        ("100:00:00", 360000),  # au-delà de 99 h, pas de troncature
    ],
)
def test_to_seconds_lit_les_formes_valides(brut, attendu):
    assert to_seconds(brut) == attendu
    assert to_seconds(brut, strict=True) == attendu


@pytest.mark.parametrize("brut", ["", None, "01:23:45.6", "pas un temps"])
def test_to_seconds_sur_l_illisible(brut):
    """Le zéro convient à un cumul ; `strict` sépare « pas de durée » de « illisible ».

    C'est la distinction qu'`oktime` porte volontairement : `00:00:00` vaut 0 des
    deux côtés, mais `01:23:45.6` — que `normalize_time` laisse passer — est une
    perte de donnée qui doit se journaliser, pas un zéro silencieux.
    """
    assert to_seconds(brut) == 0
    assert to_seconds(brut, strict=True) is None


def test_fmt_seconds_est_l_inverse_de_to_seconds():
    assert fmt_seconds(5025) == "01:23:45"
    assert fmt_seconds(0) == "00:00:00"
    assert to_seconds(fmt_seconds(9999)) == 9999
