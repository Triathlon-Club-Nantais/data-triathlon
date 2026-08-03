"""Politique de provisionnement — certification, liste d'autorisation, résolution."""
import logging

import pytest

from app.core.config import get_settings
from app.models.identity import Identity
from app.models.user import User
from app.repositories import identity_repository, user_repository
from app.services.auth import provisioning
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import ExternalIdentity


def _identite(**surcharges) -> ExternalIdentity:
    valeurs = {
        "provider": "github",
        "subject": "583231",
        "email": "contributeur@exemple.fr",
        "email_verified": True,
        "display_name": "contributeur",
    }
    valeurs.update(surcharges)
    return ExternalIdentity(**valeurs)


def test_une_premiere_connexion_cree_utilisateur_et_identite(db_session):
    user = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    assert user.email == "contributeur@exemple.fr"
    assert user.display_name == "contributeur"
    assert db_session.query(User).count() == 1
    identity = db_session.query(Identity).one()
    assert (identity.provider, identity.subject) == ("github", "583231")
    assert identity.user_id == user.id


def test_une_identite_connue_ne_cree_rien(db_session):
    premier = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    second = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    assert second.id == premier.id
    assert db_session.query(User).count() == 1
    assert db_session.query(Identity).count() == 1


def test_la_resolution_se_fait_par_le_couple_seul(db_session, monkeypatch):
    """FR-002 : ni l'adresse, ni le login — le `subject` chez ce fournisseur.

    Les deux adresses sont autorisées : la liste est réévaluée à **chaque**
    connexion, et ce test-ci porte sur la résolution, pas sur le portail.
    """
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "contributeur@exemple.fr,autre@exemple.fr")
    get_settings.cache_clear()

    premier = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    revenu = provisioning.resolve_user(
        db_session, _identite(email="autre@exemple.fr", display_name="renomme")
    )
    db_session.commit()

    assert revenu.id == premier.id


def test_une_adresse_deja_connue_donne_un_nouvel_utilisateur(db_session, monkeypatch):
    """FR-003 : c'est ce qui ferme la prise de contrôle par pré-inscription.

    Un attaquant ouvrant chez un fournisseur laxiste un compte portant l'adresse
    d'un contributeur ne doit jamais se retrouver rattaché à son compte.
    """
    premier = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    second = provisioning.resolve_user(
        db_session, _identite(provider="ailleurs", subject="autre-subject")
    )
    db_session.commit()

    assert second.id != premier.id
    assert db_session.query(User).count() == 2
    assert db_session.query(Identity).count() == 2


def test_l_adresse_est_rafraichie_a_la_reconnexion(db_session, monkeypatch):
    """FR-008 : les attributs mutables suivent le fournisseur, sans doublon."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "contributeur@exemple.fr,nouvelle@exemple.fr")
    get_settings.cache_clear()

    user = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    provisioning.resolve_user(
        db_session, _identite(email="nouvelle@exemple.fr", display_name="nouveau nom")
    )
    db_session.commit()

    db_session.refresh(user)
    assert user.email == "nouvelle@exemple.fr"
    assert user.display_name == "nouveau nom"
    assert db_session.query(Identity).one().email == "nouvelle@exemple.fr"


def test_une_adresse_non_certifiee_est_refusee(db_session):
    """FR-005 : le refus intervient **avant** l'examen de la liste."""
    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite(email_verified=False))

    assert refus.value.code == "email_unverified"


def test_une_adresse_non_certifiee_est_refusee_meme_si_autorisee(db_session, monkeypatch):
    """L'ordre compte : certification d'abord, liste ensuite (FR-005)."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "contributeur@exemple.fr")
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite(email_verified=False))

    assert refus.value.code == "email_unverified"


def test_une_adresse_hors_liste_est_refusee(db_session):
    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite(email="inconnu@exemple.fr"))

    assert refus.value.code == "account_not_allowed"


def test_un_refus_hors_liste_journalise_l_adresse(db_session, caplog):
    """Sans elle, un refus n'est pas diagnosticable.

    Le code d'erreur rendu au visiteur est volontairement muet (FR-030) : il ne
    dit pas *quelle* adresse a été soumise. Côté exploitant, c'est la seule
    information qui permette d'agir — ajouter l'adresse à la liste, ou constater
    qu'elle n'a rien à y faire. Une adresse n'est pas un secret au sens de
    FR-038, que `test_no_secret_logged` borne aux jetons et aux clés.
    """
    with caplog.at_level(logging.INFO):
        with pytest.raises(LoginError):
            provisioning.resolve_user(db_session, _identite(email="inconnu@exemple.fr"))

    assert "inconnu@exemple.fr" in caplog.text


def test_une_adresse_non_certifiee_n_est_pas_journalisee(db_session, caplog):
    """L'asymétrie est voulue : le fournisseur ne certifie pas cette adresse.

    Rien à faire pour l'exploitant — la vérification appartient au visiteur chez
    son fournisseur — et journaliser une adresse non prouvée reviendrait à
    inscrire dans nos traces une valeur que n'importe qui peut déclarer.
    """
    with caplog.at_level(logging.INFO):
        with pytest.raises(LoginError):
            provisioning.resolve_user(
                db_session, _identite(email="usurpee@exemple.fr", email_verified=False)
            )

    assert "usurpee@exemple.fr" not in caplog.text


def test_une_liste_vide_interdit_toute_connexion(db_session, monkeypatch):
    """FR-007, fail-closed : vide n'a jamais valu « tout le monde »."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite())

    assert refus.value.code == "account_not_allowed"


def test_la_liste_ignore_la_casse_et_les_espaces(db_session, monkeypatch):
    """Une adresse saisie à la main dans une variable d'environnement.

    Refuser `Contributeur@Exemple.fr` là où la liste porte l'adresse en
    minuscules serait un piège d'exploitation, pas une garantie.
    """
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", " Contributeur@Exemple.FR ")
    get_settings.cache_clear()

    user = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    assert user.email == "contributeur@exemple.fr"


def test_un_refus_ne_laisse_ni_utilisateur_ni_identite(db_session):
    """FR-006 / SC-003 : un échec n'enregistre **jamais** personne."""
    for identite in (_identite(email_verified=False), _identite(email="inconnu@exemple.fr")):
        with pytest.raises(LoginError):
            provisioning.resolve_user(db_session, identite)

    assert db_session.query(User).count() == 0
    assert db_session.query(Identity).count() == 0


def test_aucune_liaison_implicite_entre_deux_identites(db_session, monkeypatch):
    """FR-004 : aucune identité n'est créée à partir d'une autre."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "contributeur@exemple.fr")
    get_settings.cache_clear()
    user = user_repository.create(db_session, email="contributeur@exemple.fr", display_name="x")
    identity_repository.create(
        db_session,
        user_id=user.id,
        provider="ailleurs",
        subject="1",
        email="contributeur@exemple.fr",
    )
    db_session.commit()

    nouveau = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    assert nouveau.id != user.id
    assert db_session.query(Identity).filter_by(user_id=user.id).count() == 1
