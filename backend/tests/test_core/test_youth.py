"""Les épreuves jeunes ne sont pas importées (#881, décision du 30/09).

Jusqu'à Minime inclus : Mini-poussin, Poussin, Pupille, Benjamin, Minime, ou
« jeunes ». Cadets et juniors restent importés.
"""
import pytest

from app.core.youth import is_youth


@pytest.mark.parametrize("event_name", [
    "Triathlon de Mesquer - Poussins",
    "Triathlon de Mesquer - Mini-Poussins",
    "Aquathlon Pupilles",
    "Duathlon Benjamins-Minimes",
    "Triathlon Benjamines",
    "Duathlon jeunes",
    "Triathlon Avenir Jeune 6-9 ans",
    # #1255, rescrape Klikego du 07/10 : libellé jeune, catégorie absente ou fausse.
    "DUATHLON 6-9 ANS (2026)",
    "Kids 2019 et 2020",
    "Course 13-15 ans",
    "Course 9-12 ans",
    "DUATHLON KIDS (nés 2014-2017)",
    "Triathlon 6/9 ans - Avenir 1",
    "Course des enfants (nées en 2016)",
])
def test_youth_heats_are_recognised_by_name(event_name):
    assert is_youth(event_name, "S1") is True


@pytest.mark.parametrize("category", ["MPO", "MIH","MIF", "BEF", "POH", "PUF", "MPH", "MI", "BE", "Minime", "Benjamin H", "MI H", "be f"])
def test_youth_rows_are_recognised_by_category(category):
    assert is_youth("Triathlon S", category) is True


@pytest.mark.parametrize(("event_name", "category"), [
    ("Triathlon S", "CAH"),          # cadets : importés
    ("Triathlon S", "JUF"),          # juniors : importés
    ("Triathlon Cadets-Juniors", "CAH"),
    ("Triathlon S", "S1H"),
    ("Triathlon S", "M1F"),          # master, pas minime
    ("Triathlon M", ""),
    ("Trail des Minimoys", "SEH"),   # le mot doit être entier
    ("Course 16-19 ans", ""),        # cadets et juniors : importés
    ("Trail 2026 (nés avant 2008)", ""),
])
def test_other_rows_are_imported(event_name, category):
    assert is_youth(event_name, category) is False


def test_birth_years_are_read_against_the_race_year():
    """Revue #1255 : nés 2008-2009 étaient minimes en 2022, plus en 2026."""
    assert is_youth("Course (nés 2008-2009)", "", event_year=2022) is True
    assert is_youth("Course (nés 2008-2009)", "", event_year=2026) is False
