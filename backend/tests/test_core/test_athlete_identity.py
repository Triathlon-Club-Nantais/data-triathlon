"""Normalized athlete identity key (#907)."""
import pytest

from app.core.athlete_identity import athlete_identity_keys, identity_key


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Léo", "leo"),
        ("RONFLÉ", "ronfle"),
        ("Maëva", "maeva"),
        ("L'APPARTIEN", "lappartien"),
        ("L APPARTIEN", "lappartien"),
        ("LE GLOANIC", "legloanic"),
        ("LEGLOANIC", "legloanic"),
        ("Jean-marie", "jeanmarie"),
        ("Jean Marie", "jeanmarie"),
        ("Œuvray", "oeuvray"),
        ("Lætitia", "laetitia"),
        ("Strauß", "strauss"),
        ("CIC 7", "cic7"),
        ("?DOSSARD #12", "dossard12"),
        ("Иванов", "иванов"),
        ("  Dupont  ", "dupont"),
        ("?", ""),
        ("-", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_identity_key(raw, expected):
    assert identity_key(raw) == expected


def test_digits_keep_numbered_teams_apart():
    assert identity_key("CIC 7") != identity_key("CIC 9")


def test_keys_of_a_full_identity():
    assert athlete_identity_keys("LETORT", "Léo") == ("letort", "leo")


def test_an_empty_first_name_keeps_an_empty_key():
    assert athlete_identity_keys("DUPONT JEAN", "") == ("dupontjean", "")
    assert athlete_identity_keys("DUPONT", None) == ("dupont", "")


def test_a_last_name_without_identity_gives_no_key():
    assert athlete_identity_keys("?", "Jean") == (None, None)
    assert athlete_identity_keys("", "") == (None, None)
