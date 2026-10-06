import pytest

from app.core import counter_scope
from app.core.club import ClubLabels, counts_by_label, is_club_scope, is_tcn, normalize_club
from app.core.counter_scope import DEFAULT_TCN_CLUB_LABELS
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
    for label in DEFAULT_TCN_CLUB_LABELS:
        assert normalize_club(label) == label


def test_is_club_scope():
    assert is_club_scope("club") is True
    assert is_club_scope(None) is False
    assert is_club_scope("tous") is False


def test_club_labels_split_clear_and_ambiguous_entries():
    labels = ClubLabels.from_entries([("tcn", True), ("tri club nantais", False)])

    assert labels.clear == frozenset({"tri club nantais"})
    assert labels.ambiguous == frozenset({"tcn"})


def test_an_ambiguous_label_does_not_count_by_its_label_alone():
    labels = ClubLabels(clear=frozenset({"tri club nantais"}), ambiguous=frozenset({"tcn"}))

    assert labels.counts_by_label("  TRI  Club Nantais ") is True
    assert labels.counts_by_label("TCN") is False
    assert labels.counts_by_label("ASPTT") is False
    assert labels.counts_by_label(None) is False


def test_from_registry_reads_the_three_sets():
    counter_scope.load(
        disciplines=set(), club_labels={"tcn", "tri club nantais"}, ambiguous_club_labels={"tcn"}
    )

    assert ClubLabels.from_registry() == ClubLabels(
        clear=frozenset({"tri club nantais"}), ambiguous=frozenset({"tcn"})
    )
    assert counts_by_label("TCN") is False
    assert counts_by_label("Tri Club Nantais") is True


def test_an_ambiguous_label_outside_the_scope_is_ignored():
    counter_scope.load(disciplines=set(), club_labels={"tri club nantais"}, ambiguous_club_labels={"tcn"})

    assert ClubLabels.from_registry().ambiguous == frozenset()
