"""Édition du registre d'alias de club (#635)."""
import pytest

from app.core.exceptions import DomainError, DuplicateError, NotFoundError
from app.repositories import club_alias_repository, user_repository
from app.services import club_alias


def _admin(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return admin


def test_add_entry_normalise_l_alias(db_session):
    admin = _admin(db_session)

    entree = club_alias.add_entry(
        db_session, canonical_name="Racing Club Nantais", alias="RACING  CLUB NANTAIS",
        admin_user_id=admin.id,
    )

    assert entree.alias_normalized == "racing club nantais"
    assert entree.canonical_name == "Racing Club Nantais"


def test_add_entry_conserve_le_nom_canonique_tel_quel(db_session):
    """Contrairement à l'alias, le nom canonique n'est pas normalisé : c'est
    la forme d'affichage choisie par l'administrateur — seuls les bords sont
    coupés."""
    entree = club_alias.add_entry(
        db_session, canonical_name="  Racing  Club Nantais  ", alias="rcn", admin_user_id=None,
    )

    assert entree.canonical_name == "Racing  Club Nantais"


def test_add_entry_refuse_un_alias_vide(db_session):
    with pytest.raises(DomainError, match="vide"):
        club_alias.add_entry(db_session, canonical_name="RCN", alias="   ", admin_user_id=None)


def test_add_entry_refuse_un_nom_canonique_vide(db_session):
    with pytest.raises(DomainError, match="vide"):
        club_alias.add_entry(db_session, canonical_name="   ", alias="rcn", admin_user_id=None)


def test_add_entry_refuse_un_alias_deja_rattache(db_session):
    club_alias.add_entry(db_session, canonical_name="Racing Club Nantais", alias="rcn", admin_user_id=None)

    with pytest.raises(DuplicateError, match="déjà rattaché"):
        club_alias.add_entry(db_session, canonical_name="Un Autre Nom", alias="RCN", admin_user_id=None)


def test_remove_entry_retire_la_ligne(db_session):
    entree = club_alias.add_entry(db_session, canonical_name="RCN", alias="rcn", admin_user_id=None)
    db_session.flush()

    club_alias.remove_entry(db_session, entry_id=entree.id)
    db_session.flush()

    assert club_alias_repository.list_entries(db_session) == []


def test_remove_entry_refuse_un_identifiant_inconnu(db_session):
    with pytest.raises(NotFoundError):
        club_alias.remove_entry(db_session, entry_id=4242)
