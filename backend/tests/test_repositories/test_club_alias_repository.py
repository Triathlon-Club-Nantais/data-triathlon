"""Le registre d'alias de club (#635) — une table, dénormalisée par nom canonique."""
import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories import club_alias_repository, user_repository


def _admin(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return admin


def test_list_entries_rend_une_liste_vide_sur_base_vierge(db_session):
    assert club_alias_repository.list_entries(db_session) == []


def test_create_entry_pose_la_ligne(db_session):
    admin = _admin(db_session)

    entree = club_alias_repository.create_entry(
        db_session,
        canonical_name="Racing Club Nantais",
        alias_normalized="rcn 44",
        created_by_user_id=admin.id,
    )
    db_session.flush()

    assert entree.id is not None
    assert entree.canonical_name == "Racing Club Nantais"
    assert entree.alias_normalized == "rcn 44"
    assert entree.created_by_user_id == admin.id
    assert entree.created_at is not None


def test_create_entry_accepte_une_entree_sans_auteur(db_session):
    entree = club_alias_repository.create_entry(
        db_session, canonical_name="RCN", alias_normalized="rcn", created_by_user_id=None
    )

    assert entree.created_by_user_id is None


def test_la_base_refuse_un_doublon_d_alias(db_session):
    """L'unicité porte sur l'alias seul : un libellé ne peut pas être rattaché
    à deux clubs différents, même via deux administrateurs simultanés."""
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="rcn",
        created_by_user_id=None,
    )
    db_session.flush()

    club_alias_repository.create_entry(
        db_session, canonical_name="Un Autre Club", alias_normalized="rcn",
        created_by_user_id=None,
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_find_by_alias_rend_lentree_correspondante(db_session):
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="rcn",
        created_by_user_id=None,
    )
    db_session.flush()

    entree = club_alias_repository.find_by_alias(db_session, alias_normalized="rcn")

    assert entree is not None
    assert entree.canonical_name == "Racing Club Nantais"


def test_find_by_alias_rend_none_si_absent(db_session):
    assert club_alias_repository.find_by_alias(db_session, alias_normalized="rcn") is None


def test_delete_entry_retire_la_ligne(db_session):
    entree = club_alias_repository.create_entry(
        db_session, canonical_name="RCN", alias_normalized="rcn", created_by_user_id=None
    )
    db_session.flush()

    club_alias_repository.delete_entry(db_session, entree)
    db_session.flush()

    assert club_alias_repository.list_entries(db_session) == []


def test_canonical_map_associe_chaque_alias_a_son_nom_canonique(db_session):
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="rcn",
        created_by_user_id=None,
    )
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="racing club nantais",
        created_by_user_id=None,
    )
    db_session.flush()

    assert club_alias_repository.canonical_map(db_session) == {
        "rcn": "Racing Club Nantais",
        "racing club nantais": "Racing Club Nantais",
    }


def test_aliases_for_canonical_rend_les_alias_du_groupe(db_session):
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="rcn",
        created_by_user_id=None,
    )
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="racing club nantais",
        created_by_user_id=None,
    )
    club_alias_repository.create_entry(
        db_session, canonical_name="ASPTT", alias_normalized="asptt nantes",
        created_by_user_id=None,
    )
    db_session.flush()

    assert club_alias_repository.aliases_for_canonical(db_session, "Racing Club Nantais") == {
        "rcn", "racing club nantais",
    }


def test_aliases_for_canonical_compare_les_formes_normalisees(db_session):
    """La comparaison porte sur la forme normalisée du nom canonique demandé —
    pas d'égalité stricte sur la casse ou les espaces."""
    club_alias_repository.create_entry(
        db_session, canonical_name="Racing Club Nantais", alias_normalized="rcn",
        created_by_user_id=None,
    )
    db_session.flush()

    assert club_alias_repository.aliases_for_canonical(db_session, "  racing  club nantais ") == {
        "rcn"
    }


def test_aliases_for_canonical_rend_un_ensemble_vide_pour_un_nom_inconnu(db_session):
    assert club_alias_repository.aliases_for_canonical(db_session, "Club Inconnu") == set()
