import pytest

from app.core.club import TCN_CLUB_LABELS, is_club_scope, is_tcn, normalize_club
from tests.club_corpus import CORPUS


@pytest.mark.parametrize("libelle,attendu", CORPUS)
def test_is_tcn_sur_le_corpus(libelle, attendu):
    assert is_tcn(libelle) is attendu


def test_normalize_club_aplatit_casse_bords_et_espaces():
    assert normalize_club("  TRI   CLUB  NANTAIS ") == "tri club nantais"
    assert normalize_club(None) == ""
    assert normalize_club("") == ""


def test_les_libelles_de_reference_sont_deja_normalises():
    """La liste blanche est comparée à des formes normalisées : elle doit l'être."""
    for label in TCN_CLUB_LABELS:
        assert normalize_club(label) == label


def test_is_club_scope():
    assert is_club_scope("club") is True
    assert is_club_scope(None) is False
    assert is_club_scope("tous") is False
