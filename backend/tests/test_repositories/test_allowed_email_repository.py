"""Accès données de la liste d'autorisation (#170).

La normalisation est éprouvée **ici**, et pas seulement plus haut : c'est le
repository qui est le point de passage unique, et c'est elle qui rend la
contrainte `UNIQUE` suffisante.
"""
from app.repositories import allowed_email_repository, user_repository


def test_exists_ignore_la_casse_et_les_espaces(db_session):
    allowed_email_repository.add(db_session, email="Contributeur@Exemple.FR")

    assert allowed_email_repository.exists(db_session, "contributeur@exemple.fr")
    assert allowed_email_repository.exists(db_session, "  CONTRIBUTEUR@EXEMPLE.FR  ")


def test_exists_est_faux_sur_une_adresse_absente(db_session):
    assert not allowed_email_repository.exists(db_session, "inconnu@exemple.fr")


def test_add_range_l_adresse_normalisee(db_session):
    entree, creee = allowed_email_repository.add(db_session, email=" Vous@Exemple.FR ")

    assert creee is True
    assert entree.email == "vous@exemple.fr"


def test_add_est_idempotent_et_ne_cree_pas_de_doublon(db_session):
    premiere, creee = allowed_email_repository.add(db_session, email="a@exemple.fr")
    seconde, recreee = allowed_email_repository.add(db_session, email="A@Exemple.FR")

    assert creee is True
    assert recreee is False
    assert seconde.id == premiere.id
    assert len(allowed_email_repository.list_all(db_session)) == 1


def test_add_conserve_l_auteur_de_la_premiere_inscription(db_session):
    premier = user_repository.create(db_session, email="admin@exemple.fr")
    second = user_repository.create(db_session, email="autre@exemple.fr")

    allowed_email_repository.add(
        db_session, email="a@exemple.fr", created_by_user_id=premier.id
    )
    entree, _ = allowed_email_repository.add(
        db_session, email="a@exemple.fr", created_by_user_id=second.id
    )

    assert entree.created_by_user_id == premier.id


def test_list_all_est_triee_par_adresse_et_porte_son_auteur(db_session):
    auteur = user_repository.create(
        db_session, email="admin@exemple.fr", display_name="Camille Durand"
    )
    allowed_email_repository.add(db_session, email="zoe@exemple.fr")
    allowed_email_repository.add(
        db_session, email="alex@exemple.fr", created_by_user_id=auteur.id
    )

    lignes = allowed_email_repository.list_all(db_session)

    assert [ligne.email for ligne in lignes] == ["alex@exemple.fr", "zoe@exemple.fr"]
    assert lignes[0].created_by.display_name == "Camille Durand"
    assert lignes[1].created_by is None


def test_list_all_charge_l_auteur_en_une_requete(db_session):
    """Trente lignes valent une requête, pas trente et une.

    `unloaded` dit ce que l'ORM devrait aller rechercher à l'accès : y voir
    `created_by` signalerait un `joinedload` perdu, donc un N+1 sur l'écran.
    """
    from sqlalchemy import inspect

    auteur = user_repository.create(db_session, email="admin@exemple.fr")
    for rang in range(3):
        allowed_email_repository.add(
            db_session, email=f"a{rang}@exemple.fr", created_by_user_id=auteur.id
        )
    db_session.commit()
    db_session.expunge_all()

    lignes = allowed_email_repository.list_all(db_session)

    assert all("created_by" not in inspect(ligne).unloaded for ligne in lignes)


def test_get_rend_la_ligne_ou_none(db_session):
    entree, _ = allowed_email_repository.add(db_session, email="a@exemple.fr")

    assert allowed_email_repository.get(db_session, entree.id) is entree
    assert allowed_email_repository.get(db_session, entree.id + 999) is None


def test_delete_retire_la_ligne(db_session):
    entree, _ = allowed_email_repository.add(db_session, email="a@exemple.fr")

    allowed_email_repository.delete(db_session, entree)

    assert allowed_email_repository.list_all(db_session) == []
    assert not allowed_email_repository.exists(db_session, "a@exemple.fr")
