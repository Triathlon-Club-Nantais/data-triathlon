"""Les entrées qui bornent les compteurs (#95) — une table, deux natures.

Les deux natures ont la même forme (une chaîne dans un ensemble, avec sa
provenance) et vivent donc dans la même table, discriminées par `kind`.
"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.models.counter_scope_entry import CLUB_LABEL, NON_FEDERAL_DISCIPLINE
from app.repositories import counter_scope_repository, user_repository


def _admin(db_session):
    admin = user_repository.create(db_session, email="admin@exemple.fr", display_name="Admin")
    db_session.flush()
    return admin


def test_list_entries_rend_une_liste_vide_sur_base_vierge(db_session):
    assert counter_scope_repository.list_entries(db_session, kind=CLUB_LABEL) == []


def test_create_entry_pose_la_ligne(db_session):
    admin = _admin(db_session)

    entree = counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn 44", created_by_user_id=admin.id
    )
    db_session.flush()

    assert entree.id is not None
    assert entree.kind == CLUB_LABEL
    assert entree.value == "tcn 44"
    assert entree.created_by_user_id == admin.id
    assert entree.created_at is not None


def test_create_entry_accepte_une_entree_sans_auteur(db_session):
    """Les lignes d'amorçage de la migration n'en ont pas."""
    entree = counter_scope_repository.create_entry(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail", created_by_user_id=None
    )

    assert entree.created_by_user_id is None


def test_list_entries_ne_rend_que_la_nature_demandee(db_session):
    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    counter_scope_repository.create_entry(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail", created_by_user_id=None
    )
    db_session.flush()

    libelles = counter_scope_repository.list_entries(db_session, kind=CLUB_LABEL)

    assert [entree.value for entree in libelles] == ["tcn"]


def test_list_entries_sans_nature_rend_tout_trie_par_valeur(db_session):
    for valeur in ("tri club nantais", "tcn"):
        counter_scope_repository.create_entry(
            db_session, kind=CLUB_LABEL, value=valeur, created_by_user_id=None
        )
    db_session.flush()

    entrees = counter_scope_repository.list_entries(db_session)

    assert [entree.value for entree in entrees] == ["tcn", "tri club nantais"]


def test_delete_entry_retire_la_ligne(db_session):
    entree = counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    db_session.flush()

    counter_scope_repository.delete_entry(db_session, entree)
    db_session.flush()

    assert counter_scope_repository.list_entries(db_session, kind=CLUB_LABEL) == []


def test_get_entry_ne_rend_rien_pour_une_autre_nature(db_session):
    """Un `id` de discipline demandé sous la nature « libellé » est un 404,
    jamais l'entrée de l'autre liste."""
    entree = counter_scope_repository.create_entry(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail", created_by_user_id=None
    )
    db_session.flush()

    assert counter_scope_repository.get_entry(db_session, kind=CLUB_LABEL, entry_id=entree.id) is None


def test_count_entries_compte_par_nature(db_session):
    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    counter_scope_repository.create_entry(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail", created_by_user_id=None
    )
    db_session.flush()

    assert counter_scope_repository.count_entries(db_session, kind=CLUB_LABEL) == 1


def test_la_base_refuse_un_doublon_de_nature_et_valeur(db_session):
    """La contrainte d'unicité, pas seulement la validation applicative : deux
    administrateurs qui écrivent en même temps ne créent pas de doublon."""
    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    db_session.flush()

    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="tcn", created_by_user_id=None
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_la_meme_valeur_est_permise_dans_les_deux_natures(db_session):
    """L'unicité porte sur le couple, pas sur la valeur seule."""
    counter_scope_repository.create_entry(
        db_session, kind=CLUB_LABEL, value="trail", created_by_user_id=None
    )
    counter_scope_repository.create_entry(
        db_session, kind=NON_FEDERAL_DISCIPLINE, value="trail", created_by_user_id=None
    )

    db_session.flush()

    assert counter_scope_repository.count_entries(db_session, kind=CLUB_LABEL) == 1
