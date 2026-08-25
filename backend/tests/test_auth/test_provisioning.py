"""Politique de provisionnement — certification, liste d'autorisation, résolution.

Depuis #170 la liste d'autorisation vit **en base** : les tests l'alimentent par
la fixture `autoriser`, jamais par une variable d'environnement. C'est ce qui
rend le portail réévaluable sans redémarrage, et c'est éprouvé ici même
(`test_une_adresse_ajoutee_est_effective_sans_redemarrage`).
"""
import logging

import pytest

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


def test_la_resolution_se_fait_par_le_couple_seul(db_session, autoriser):
    """FR-002 : ni l'adresse, ni le login — le `subject` chez ce fournisseur.

    Les deux adresses sont autorisées : la liste est réévaluée à **chaque**
    connexion, et ce test-ci porte sur la résolution, pas sur le portail.
    """
    autoriser("autre@exemple.fr")

    premier = provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    revenu = provisioning.resolve_user(
        db_session, _identite(email="autre@exemple.fr", display_name="renomme")
    )
    db_session.commit()

    assert revenu.id == premier.id


def test_une_adresse_deja_connue_donne_un_nouvel_utilisateur(db_session):
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


def test_l_adresse_est_rafraichie_a_la_reconnexion(db_session, autoriser):
    """FR-008 : les attributs mutables suivent le fournisseur, sans doublon."""
    autoriser("nouvelle@exemple.fr")

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


def test_la_certification_est_examinee_avant_la_liste(
    db_session, vider_la_liste_autorisation
):
    """FR-005 : l'ordre ne se voit que sur une adresse qui échoue aux **deux**
    contrôles — c'est le seul cas où les deux codes sont candidats, et où celui
    qui est rendu dit lequel des deux a tranché.

    Le test précédent ne le prouve pas : la fixture autouse `liste_autorisation`
    autorise l'adresse de `_identite()`, donc la seconde porte y est ouverte et
    ne peut rien refuser.
    """
    vider_la_liste_autorisation()

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


def test_une_liste_vide_interdit_toute_connexion(db_session, vider_la_liste_autorisation):
    """FR-004, fail-closed : vide n'a jamais valu « tout le monde ».

    Le garde de configuration ne pèse plus la liste depuis #170 : c'est **ici**,
    et nulle part ailleurs, que le fail-closed se joue.
    """
    vider_la_liste_autorisation()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite())

    assert refus.value.code == "account_not_allowed"


def test_la_liste_ignore_la_casse_et_les_espaces(
    db_session, vider_la_liste_autorisation, autoriser
):
    """Une adresse saisie à la main dans un formulaire d'administration.

    Refuser `Contributeur@Exemple.fr` là où la liste porte l'adresse en
    minuscules serait un piège d'exploitation, pas une garantie.
    """
    vider_la_liste_autorisation()
    autoriser(" Contributeur@Exemple.FR ")

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


def test_aucune_liaison_implicite_entre_deux_identites(db_session):
    """FR-004 : aucune identité n'est créée à partir d'une autre."""
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


def test_une_adresse_ajoutee_est_effective_sans_redemarrage(
    db_session, vider_la_liste_autorisation, autoriser
):
    """FR-002 : la liste est relue à **chaque** tentative, sans cache.

    C'est la propriété qui *est* la feature. Le défaut que #170 corrige était un
    `lru_cache` sur `Settings` : la liste n'était lue qu'au démarrage, et ajouter
    un contributeur exigeait un redéploiement. Le test refuse, inscrit, puis
    retente **dans le même processus**, sans rien réinitialiser — ni cache vidé,
    ni session rouverte.
    """
    vider_la_liste_autorisation()
    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite())
    assert refus.value.code == "account_not_allowed"

    autoriser("contributeur@exemple.fr")

    user = provisioning.resolve_user(db_session, _identite())
    db_session.commit()
    assert user.email == "contributeur@exemple.fr"


def test_un_retrait_est_effectif_a_la_tentative_suivante(
    db_session, vider_la_liste_autorisation
):
    """Le pendant du précédent : retirer ferme la connexion suivante."""
    provisioning.resolve_user(db_session, _identite())
    db_session.commit()

    vider_la_liste_autorisation()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identite())
    assert refus.value.code == "account_not_allowed"
