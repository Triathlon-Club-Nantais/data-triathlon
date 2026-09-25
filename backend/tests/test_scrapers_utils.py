"""Tests unitaires pour le helper de reconnaissance de statut (sans réseau)."""
from datetime import date

import pytest

from app.scrapers.utils import (
    derive_status_from_label,
    fmt_seconds,
    gender_from_category,
    normalize_time,
    parse_fr_date,
    split_athlete_name,
    split_relay_teammates,
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
    # Hors délai (barrière horaire) : « OTL » d'Embrunman 350635, #970
    ("OTL", "DNF"),
    ("HD", "DNF"),
    ("Hors délai", "DNF"),
    ("Hors délais", "DNF"),
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
    # #906 : forme virgulée « NOM, Prénom » (`LFNAME` RaceResult), toute casse.
    ("DUPONT, JEAN", ("DUPONT", "JEAN")),
    ("DUPONT, Jean", ("DUPONT", "Jean")),
    ("Dupont, Jean", ("Dupont", "Jean")),
    ("BOURGAIN-VIALAR, ALBANE", ("BOURGAIN-VIALAR", "ALBANE")),
    ("MERIAUX DE SCHEPPER, HECTOR", ("MERIAUX DE SCHEPPER", "HECTOR")),
    ("  DUPONT ,  Jean Marie ", ("DUPONT", "Jean Marie")),
    # Coupe sur la première virgule seulement.
    ("DUPONT, Jean, Junior", ("DUPONT", "Jean, Junior")),
    # Un côté vide : la virgule n'est qu'une ponctuation parasite.
    ("HOFMANN,", ("HOFMANN", "")),
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
    deux côtés, mais `01:23:45.6`, lu sans `normalize_time` en amont, est une
    perte de donnée qui doit se journaliser, pas un zéro silencieux.
    """
    assert to_seconds(brut) == 0
    assert to_seconds(brut, strict=True) is None


def test_fmt_seconds_est_l_inverse_de_to_seconds():
    assert fmt_seconds(5025) == "01:23:45"
    assert fmt_seconds(0) == "00:00:00"
    assert to_seconds(fmt_seconds(9999)) == 9999


# ── Relais aux équipiers nommés (#895) : valeurs réelles du sondage ─────────


@pytest.mark.parametrize(("published", "expected"), [
    # timepulse : listes parallèles de noms et de prénoms
    ("CANNIOU/OLIVIER Cedric/Leclerc", [("CANNIOU", "Cedric"), ("OLIVIER", "Leclerc")]),
    (
        "HUREAU /HUREAU/PERDREAU Régis /Marianne/Jean-Sebastien",
        [("HUREAU", "Régis"), ("HUREAU", "Marianne"), ("PERDREAU", "Jean-Sebastien")],
    ),
    ("PINSON/ROCHEFORT-CUNIN Eric/Emmanuel", [("PINSON", "Eric"), ("ROCHEFORT-CUNIN", "Emmanuel")]),
    (
        "QUILLET/BRILLANT CAMPBELL/ROUSSEAU Guillaume/Alex/Jean Philippe",
        [("QUILLET", "Guillaume"), ("BRILLANT CAMPBELL", "Alex"), ("ROUSSEAU", "Jean Philippe")],
    ),
    (
        "LEGEARD/LEGEARD/LEGEARD Anne/Paul/Marc",
        [("LEGEARD", "Anne"), ("LEGEARD", "Paul"), ("LEGEARD", "Marc")],
    ),
    # klikego, oktime, chronoplace : segments « NOM PRÉNOM »
    ("MASSONNEAU PIERRE / BESANCON FABIEN .", [("MASSONNEAU", "PIERRE"), ("BESANCON", "FABIEN")]),
    ("GUILLON RÉMI / CHARPENTIER EMMANUEL", [("GUILLON", "RÉMI"), ("CHARPENTIER", "EMMANUEL")]),
    ("MENARDAIS FERDINAND / COMPAIN LENA", [("MENARDAIS", "FERDINAND"), ("COMPAIN", "LENA")]),
    ("DUPONT Jean / MARTIN Paul", [("DUPONT", "Jean"), ("MARTIN", "Paul")]),
    ("Jean DUPONT / Paul MARTIN", [("DUPONT", "Jean"), ("MARTIN", "Paul")]),
    # frontière nom/prénom indécidable
    ("LE BRAS LUC / LE PAGE GUULLAUME .", None),
    ("LE BOZEC HENRI / BABINET SYLVAIN", None),
    ("DAUGUET PIERRE E. / BELMONTE ALEXANDRE .", None),
    ("MARTIN Jean DUPONT / Paul", None),
    # un segment sans nom et prénom
    ("DAMIEN/FRANCOIS Francois et Benjamin", None),
    ("ECN / USCAL Sarah et Francois", None),
    ("FRATERIES POZZEBON/SKLADZIEN", None),
    # groupes, prénoms seuls, initiales : aucun `/`
    ("LES BARBAPAPAS Alex et Margot", None),
    ("TIC & TAC .", None),
    ("OGGY ET LES CAFARDES", None),
    ("CREUSOTRI", None),
    ("LA COUSINADE", None),
    ("GUILLAUME & ANTHONY", None),
    ("S. D.", None),
    ("", None),
    # listes de longueurs différentes, doublons, effectif hors bornes
    ("AUBERT/BLANC/COLIN Jean/Paul", None),
    ("DUPONT Jean / DUPONT Jean", None),
    ("DUPONT Jéan / DUPONT Jean", None),
    (" / ".join(f"NOM{chr(65 + i)}X PRENOM{chr(65 + i)}X" for i in range(9)), None),
    ("DUPONT Jean & Marie / MARTIN Paul", None),
    ("DUPONT/MARTIN Jean et Luc/Paul", None),
    ("DUPONT/MARTIN Jean & Luc/Paul", None),
])
def test_split_relay_teammates(published, expected):
    assert split_relay_teammates(published) == expected


def test_split_relay_teammates_accepts_eight():
    published = " / ".join(f"NOM{chr(65 + i)}X PRENOM{chr(65 + i)}X" for i in range(8))
    assert len(split_relay_teammates(published)) == 8


# Catégories relevées sur 17 épreuves RaceResult sans colonne sexe (#990).
@pytest.mark.parametrize("category,expected", [
    ("S1M", "M"), ("M2F", "F"), ("JUM", "M"), ("MIF", "F"), ("MPF", "F"),
    ("U23M", "M"), ("M1-3M", "M"), ("M4+F", "F"),
    ("M18-34", "M"), ("F6-8", "F"), ("M65+", "M"),
    ("Seniors F", "F"), ("Masters H", "M"), ("Cadets H", "M"),
    ("Master 4+ Homme", "M"),
])
def test_gender_from_category_reads_individual_categories(category, expected):
    assert gender_from_category(category) == expected


# Un libellé de sexe nu (« Masculin », « Hommes ») n'est mesuré que sur des
# relais et des duos : il décrit la composition de l'équipe, pas une personne.
@pytest.mark.parametrize("category", [
    "", "Masculin", "Féminin", "Hommes", "Femmes", "Mixte", "Relais Masculin",
    "Relais Féminin", "M+F", "DNF", "DNS", "1", "SE", "FEM", "M4+",
])
def test_gender_from_category_leaves_team_and_unreadable_categories_empty(category):
    assert gender_from_category(category) == ""


@pytest.mark.parametrize("raw,expected", [
    # Klikego, courses 199 à 203 : millièmes après la seconde (#969).
    ("00:12'15\"000", "00:12:15"),
    ("00:12'15''000", "00:12:15"),
    # Sport Innovation « Temps Officiel (Réel) » : l'officiel d'abord (#969).
    ("00:06:41 (00:06:45)", "00:06:41"),
])
def test_normalize_time_reads_klikego_and_sportinnovation_forms(raw, expected):
    assert normalize_time(raw) == expected


@pytest.mark.parametrize("raw,expected", [
    # Minutes au-delà de l'heure : `00:65:30` n'est pas une durée (#969).
    ("65:30", "01:05:30"),
    ("125:07", "02:05:07"),
    ("59:59", "00:59:59"),
    # Fraction de seconde tronquée, point ou virgule (#969).
    ("1:05:30.4", "01:05:30"),
    ("02:35:01,7", "02:35:01"),
    ("00:57:33.2510000", "00:57:33"),
    ("39:11.25", "00:39:11"),
])
def test_normalize_time_reads_long_minutes_and_fractions(raw, expected):
    assert normalize_time(raw) == expected
