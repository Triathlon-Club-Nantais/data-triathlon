"""Déaccentuation (issue #163).

Ni SQLite ni PostgreSQL ne rendent `lower()` insensible aux accents — mesuré :
`lower('LEMÉE') LIKE '%lemee%'` vaut faux sur les deux. Cette fonction est la
moitié SQLite du dispositif ; l'autre est l'extension `unaccent` de PostgreSQL.
"""
import pytest

from app.core.text import deaccent


@pytest.mark.parametrize(
    ("entree", "attendu"),
    [
        ("LEMÉE", "LEMEE"),
        ("Pléneuf-Val-André", "Pleneuf-Val-Andre"),
        ("Loïc", "Loic"),
        ("François", "Francois"),
        ("Ångström", "Angstrom"),
        ("déjà vu", "deja vu"),
        ("sans accent", "sans accent"),
        ("", ""),
    ],
)
def test_deaccent(entree, attendu):
    assert deaccent(entree) == attendu


def test_deaccent_conserve_none():
    """La fonction est enregistrée comme fonction SQLite : `NULL` doit ressortir `NULL`."""
    assert deaccent(None) is None


def test_deaccent_laisse_intactes_les_ecritures_sans_diacritiques():
    """Un idéogramme n'a pas de marque combinante : rien à retirer."""
    assert deaccent("東京") == "東京"
    assert deaccent("Москва") == "Москва"


def test_deaccent_s_applique_uniformement_hors_alphabet_latin():
    """La règle ne connaît pas les alphabets, seulement les marques combinantes.

    Le tonos grec en est une, il tombe donc comme un accent français. Sans
    conséquence pour la recherche d'athlètes, et surtout : une exception par
    écriture serait une liste à maintenir sans fin.
    """
    assert deaccent("Ολυμπία") == "Ολυμπια"
