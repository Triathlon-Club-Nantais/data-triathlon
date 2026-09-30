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
])
def test_youth_heats_are_recognised_by_name(event_name):
    assert is_youth(event_name, "") is True


@pytest.mark.parametrize("category", ["MIH", "MIF", "BEF", "POH", "PUF", "MPH", "MI", "BE", "Minime", "Benjamin H"])
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
])
def test_other_rows_are_imported(event_name, category):
    assert is_youth(event_name, category) is False
