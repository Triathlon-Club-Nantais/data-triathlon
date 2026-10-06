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
        ("Søren", "soren"),
        ("Łukasz", "lukasz"),
        ("Đorđe", "dorde"),
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


def test_a_first_name_alone_is_kept_as_a_whole_name():
    """Klikego rend `("", "Jean Dupont")` quand le premier mot n'est pas en
    majuscules : l'identité est dans le prénom, elle ne doit pas se perdre."""
    assert athlete_identity_keys("", "Jean Dupont") == ("jeandupont", "")
    assert athlete_identity_keys("-", "Jean") == ("jean", "")


def test_a_name_without_identity_gives_no_key():
    assert athlete_identity_keys("?", "-") == (None, None)
    assert athlete_identity_keys("", "") == (None, None)


@pytest.mark.parametrize(
    ("nom", "prenom", "person"),
    [
        ("ARNAUD", "& VINCENT .", ("ARNAUD", "Vincent")),
        ("JACQUES", "& DANIEL", ("DANIEL", "Jacques")),
        ("MARTIN / DURAND", "", ("MARTIN", "Durand")),
        ("Paul et Marie", "", ("PAUL", "Marie")),
        ("LUC + LEA", "", ("LUC", "Lea")),
    ],
)
def test_a_team_label_never_takes_a_person_key(nom, prenom, person):
    """#1192 : « ARNAUD & VINCENT » prenait la clé de la personne « ARNAUD Vincent »
    et la reprise des doublons fusionnait le résultat d'équipe dans la personne."""
    key = athlete_identity_keys(nom, prenom)
    assert key != athlete_identity_keys(*person)
    assert key != athlete_identity_keys(person[1], person[0])


def test_two_spellings_of_one_team_share_a_key():
    assert athlete_identity_keys("ARNAUD", "& VINCENT .") == athlete_identity_keys("Arnaud &", "Vincent")


def test_a_compound_surname_glued_by_a_slash_is_a_person():
    """Collé des deux côtés, `/` joint un nom composé, il ne sépare pas deux équipiers."""
    assert athlete_identity_keys("DUPONT/MARTIN", "Marie") == athlete_identity_keys("DUPONT-MARTIN", "Marie")


def test_a_name_holding_et_inside_a_word_is_a_person():
    assert athlete_identity_keys("BRETON", "Etienne") == ("breton", "etienne")
