"""La clé d'une opposition (#334) : ce qu'un chronométreur publie en variantes reste une seule personne."""
import pytest

from app.core.identity import identity_hash, opposition_key


@pytest.mark.parametrize(
    ("nom", "prenom"),
    [
        ("DUPONT", "Jean-Pierre"),
        ("Dupont", "Jean Pierre"),
        ("dupont", "JEAN-PIERRE "),
        ("Jean-Pierre", "DUPONT"),
        ("DUPONT JEAN-PIERRE", ""),
    ],
)
def test_published_variants_share_one_key(nom, prenom):
    assert opposition_key(nom, prenom) == opposition_key("Dupont", "Jean-Pierre")


def test_accents_and_punctuation_are_ignored():
    assert opposition_key("LEMÉE", "Zoé") == opposition_key("Lemee", "Zoe.")


def test_two_people_have_two_keys():
    assert opposition_key("Dupont", "Jean") != opposition_key("Dupont", "Jeanne")


def test_the_hash_is_a_stable_hex_digest_and_never_the_name():
    empreinte = identity_hash("Dupont", "Jean-Pierre")
    assert len(empreinte) == 64
    assert int(empreinte, 16) >= 0
    assert empreinte == identity_hash("DUPONT", "jean pierre")
    assert "dupont" not in empreinte
