"""Catégorie d'âge FFTri (#1291, research R1). Oracle : règlements FFTri 2026."""
from datetime import date

import pytest

from app.services.fftri_category import fftri_category

SEASON_2026 = date(2026, 3, 15)


@pytest.mark.parametrize(
    ("birth_year", "expected"),
    [
        (2020, "Moins de 6 ans"),
        (2019, "Mini-poussin"),
        (2018, "Mini-poussin"),
        (2017, "Poussin"),
        (2016, "Poussin"),
        (2015, "Pupille"),
        (2014, "Pupille"),
        (2013, "Benjamin"),
        (2012, "Benjamin"),
        (2011, "Minime"),
        (2010, "Minime"),
        (2009, "Cadet"),
        (2008, "Cadet"),
        (2007, "Junior"),
        (2006, "Junior"),
        (2005, "Senior"),
        (1980, "Senior"),
    ],
)
def test_season_2026_matches_the_federal_table(birth_year, expected):
    assert fftri_category(date(birth_year, 6, 1), SEASON_2026) == expected


def test_the_season_switches_on_november_first():
    born = date(2012, 1, 1)
    assert fftri_category(born, date(2026, 10, 31)) == "Benjamin"
    # 1er novembre 2026 : saison 2027, âge compté sur 2026.
    assert fftri_category(born, date(2026, 11, 1)) == "Minime"


def test_no_birth_date_gives_no_category():
    assert fftri_category(None, SEASON_2026) is None
