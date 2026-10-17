"""Politique de provisionnement : certification, adresse retenue, résolution.

Depuis #1322 la liste d'autorisation ne conditionne plus la connexion : elle
porte le rôle du premier jour et départage l'adresse retenue (FR-016). Une
adresse certifiée hors liste ouvre un compte **sans rôle**.
"""
import logging

import pytest

from app.models.identity import Identity
from app.models.user import User
from app.repositories import identity_repository, user_repository
from app.services.auth import provisioning
from app.services.auth.errors import LoginError
from app.services.auth.idp.base import ExternalIdentity


def _identity(**surcharges) -> ExternalIdentity:
    valeurs = {
        "provider": "github",
        "subject": "583231",
        "email": "contributeur@exemple.fr",
        "email_verified": True,
        "display_name": "contributeur",
    }
    valeurs.update(surcharges)
    return ExternalIdentity(**valeurs)


def test_une_premiere_connexion_cree_utilisateur_et_identity(db_session):
    user = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    assert user.email == "contributeur@exemple.fr"
    assert user.display_name == "contributeur"
    assert db_session.query(User).count() == 1
    identity = db_session.query(Identity).one()
    assert (identity.provider, identity.subject) == ("github", "583231")
    assert identity.user_id == user.id


def test_une_identite_connue_ne_cree_rien(db_session):
    premier = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    second = provisioning.resolve_user(db_session, _identity())
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

    premier = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    revenu = provisioning.resolve_user(
        db_session, _identity(email="autre@exemple.fr", display_name="renomme")
    )
    db_session.commit()

    assert revenu.id == premier.id


def test_une_adresse_deja_connue_donne_un_nouvel_utilisateur(db_session):
    """FR-003 : c'est ce qui ferme la prise de contrôle par pré-inscription.

    Un attaquant ouvrant chez un fournisseur laxiste un compte portant l'adresse
    d'un contributeur ne doit jamais se retrouver rattaché à son compte.
    """
    premier = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    second = provisioning.resolve_user(
        db_session, _identity(provider="ailleurs", subject="autre-subject")
    )
    db_session.commit()

    assert second.id != premier.id
    assert db_session.query(User).count() == 2
    assert db_session.query(Identity).count() == 2


def test_l_adresse_est_rafraichie_a_la_reconnexion(db_session, autoriser):
    """FR-008 : les attributs mutables suivent le fournisseur, sans doublon."""
    autoriser("nouvelle@exemple.fr")

    user = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    provisioning.resolve_user(
        db_session, _identity(email="nouvelle@exemple.fr", display_name="nouveau nom")
    )
    db_session.commit()

    db_session.refresh(user)
    assert user.email == "nouvelle@exemple.fr"
    assert user.display_name == "nouveau nom"
    assert db_session.query(Identity).one().email == "nouvelle@exemple.fr"


def test_une_adresse_non_certifiee_est_refusee(db_session):
    """FR-005 : le refus intervient **avant** l'examen de la liste."""
    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identity(email_verified=False))

    assert refus.value.code == "email_unverified"


def test_une_liste_vide_n_ouvre_pas_une_adresse_non_certifiee(
    db_session, vider_la_liste_autorisation
):
    """FR-011 : la certification reste exigée, liste vide ou non."""
    vider_la_liste_autorisation()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identity(email_verified=False))

    assert refus.value.code == "email_unverified"


def test_une_adresse_hors_liste_ouvre_un_compte_sans_role(db_session):
    """FR-011 / FR-015 (#1322) : la connexion n'exige plus la liste."""
    user = provisioning.resolve_user(db_session, _identity(email="inconnu@exemple.fr"))
    db_session.commit()

    assert user.email == "inconnu@exemple.fr"
    assert user.roles == []


def test_un_compte_sans_role_est_journalise(db_session, caplog):
    """Trace d'exploitation : un compte est né sans rôle. L'adresse n'y figure
    pas, l'identifiant du compte suffit à le retrouver."""
    with caplog.at_level(logging.INFO):
        user = provisioning.resolve_user(db_session, _identity(email="inconnu@exemple.fr"))

    assert f"Account created without role: user={user.id}" in caplog.text
    assert "inconnu@exemple.fr" not in caplog.text


def test_une_adresse_non_certifiee_n_est_pas_journalisee(db_session, caplog):
    """L'asymétrie est voulue : le fournisseur ne certifie pas cette adresse.

    Rien à faire pour l'exploitant — la vérification appartient au visiteur chez
    son fournisseur — et journaliser une adresse non prouvée reviendrait à
    inscrire dans nos traces une valeur que n'importe qui peut déclarer.
    """
    with caplog.at_level(logging.INFO):
        with pytest.raises(LoginError):
            provisioning.resolve_user(
                db_session, _identity(email="usurpee@exemple.fr", email_verified=False)
            )

    assert "usurpee@exemple.fr" not in caplog.text


def test_une_liste_vide_n_interdit_plus_la_connexion(db_session, vider_la_liste_autorisation):
    """#1322 : une liste vide n'ouvre aucun pouvoir, mais n'interdit plus de
    se connecter. Le fail-closed est passé aux gardes (pouvoir, code du site)."""
    vider_la_liste_autorisation()

    user = provisioning.resolve_user(db_session, _identity())

    assert user.roles == []


def test_la_liste_ignore_la_casse_et_les_espaces(
    db_session, vider_la_liste_autorisation, autoriser
):
    """Une adresse saisie à la main dans un formulaire d'administration.

    Refuser `Contributeur@Exemple.fr` là où la liste porte l'adresse en
    minuscules serait un piège d'exploitation, pas une garantie.
    """
    vider_la_liste_autorisation()
    autoriser(" Contributeur@Exemple.FR ")

    user = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    assert user.email == "contributeur@exemple.fr"


def test_un_refus_ne_laisse_ni_utilisateur_ni_identity(db_session):
    """FR-006 / SC-003 : un échec n'enregistre **jamais** personne."""
    for identite in (_identity(email_verified=False), _identity(email="")):
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

    nouveau = provisioning.resolve_user(db_session, _identity())
    db_session.commit()

    assert nouveau.id != user.id
    assert db_session.query(Identity).filter_by(user_id=user.id).count() == 1


def test_l_adresse_retenue_est_reevaluee_a_chaque_connexion(
    db_session, vider_la_liste_autorisation, autoriser
):
    """La liste est relue à **chaque** tentative, sans cache : une adresse
    inscrite après une première connexion devient l'adresse retenue à la
    suivante."""
    vider_la_liste_autorisation()
    identite = _identity(
        email="perso@gmail.com", verified_emails=("perso@gmail.com", "prenom.nom@club.fr")
    )
    user = provisioning.resolve_user(db_session, identite)
    db_session.commit()
    assert user.email == "perso@gmail.com"

    autoriser("prenom.nom@club.fr")

    provisioning.resolve_user(db_session, identite)
    db_session.commit()
    assert user.email == "prenom.nom@club.fr"


def test_un_compte_desactive_reste_refuse(db_session):
    """FR-012 : la désactivation (retrait de la liste) ferme la connexion."""
    user = provisioning.resolve_user(db_session, _identity())
    user.is_active = False
    db_session.commit()

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identity())
    assert refus.value.code == "account_not_allowed"


def test_une_secondaire_verifiee_autorisee_ouvre_la_connexion(
    db_session, autoriser, vider_la_liste_autorisation
):
    """#1059 : primaire non inscrite, secondaire vérifiée inscrite."""
    vider_la_liste_autorisation()
    autoriser("prenom.nom@club.fr")

    user = provisioning.resolve_user(
        db_session,
        _identity(
            email="perso@gmail.com",
            verified_emails=("perso@gmail.com", "prenom.nom@club.fr"),
        ),
    )
    db_session.commit()

    assert user.email == "prenom.nom@club.fr"
    assert db_session.query(Identity).one().email == "prenom.nom@club.fr"


def test_la_primaire_l_emporte_quand_plusieurs_adresses_sont_autorisees(db_session, autoriser):
    autoriser("perso@gmail.com", "prenom.nom@club.fr")

    user = provisioning.resolve_user(
        db_session,
        _identity(
            email="perso@gmail.com",
            verified_emails=("perso@gmail.com", "prenom.nom@club.fr"),
        ),
    )

    assert user.email == "perso@gmail.com"


def test_sans_adresse_autorisee_la_principale_est_retenue(
    db_session, autoriser, vider_la_liste_autorisation
):
    vider_la_liste_autorisation()
    autoriser("autre@exemple.fr")

    user = provisioning.resolve_user(
        db_session,
        _identity(email="perso@gmail.com", verified_emails=("perso@gmail.com", "b@exemple.fr")),
    )

    assert user.email == "perso@gmail.com"


def test_une_adresse_d_adherent_est_retenue_apres_la_liste_d_autorisation(
    db_session, vider_la_liste_autorisation
):
    """FR-016 : autorisation, puis liste d'adhérents qui compte, puis principale."""
    from app.core.season import season_of
    from app.core.time import utcnow
    from app.models.member_email import MemberEmail
    from app.services import membership

    vider_la_liste_autorisation()
    db_session.add(MemberEmail(email="prenom.nom@club.fr", season=season_of(utcnow().date()), source="import"))
    db_session.flush()

    user = provisioning.resolve_user(
        db_session,
        _identity(email="perso@gmail.com", verified_emails=("perso@gmail.com", "prenom.nom@club.fr")),
    )

    assert user.email == "prenom.nom@club.fr"
    assert membership.is_member(db_session, user, utcnow().date())


def test_le_role_du_premier_jour_reste_reserve_a_la_liste(
    db_session, vider_la_liste_autorisation, organisation
):
    """FR-012 : une adresse hors liste naît sans rôle ; une adresse inscrite
    avec un rôle le reçoit à la création, comme avant #1322."""
    from app.models.role import Role
    from app.repositories import allowed_email_repository

    vider_la_liste_autorisation()
    role = Role(slug="benevole", name="Bénévole", organisation_id=organisation.id)
    db_session.add(role)
    entree, _ = allowed_email_repository.add(db_session, email="inscrit@club.fr")
    allowed_email_repository.set_initial_role(db_session, entree, role_id=role.id)
    db_session.commit()

    hors_liste = provisioning.resolve_user(db_session, _identity(subject="1", email="x@exemple.fr"))
    inscrit = provisioning.resolve_user(db_session, _identity(subject="2", email="inscrit@club.fr"))
    db_session.commit()

    assert hors_liste.roles == []
    assert [attribution.role_id for attribution in inscrit.roles] == [role.id]


def test_une_adresse_autorisee_n_est_pas_remplacee_par_une_adresse_hors_liste(
    db_session, vider_la_liste_autorisation, autoriser
):
    """Revue de #1322 : le retrait d'une adresse doit encore fermer le compte.

    A certifiée et inscrite à la création, puis le fournisseur ne certifie plus
    que B. Si `users.email` passait à B, retirer A ne désactiverait personne
    (`allowed_emails.remove` cherche les comptes par leur adresse).
    """
    from app.services.auth import allowed_emails

    vider_la_liste_autorisation()
    autoriser("a@club.fr")
    acteur = user_repository.create(db_session, email="admin@club.fr", display_name="")
    user = provisioning.resolve_user(db_session, _identity(email="a@club.fr"))
    db_session.commit()

    provisioning.resolve_user(db_session, _identity(email="b@gmail.com"))
    db_session.commit()
    assert user.email == "a@club.fr"

    from app.repositories import allowed_email_repository

    allowed_emails.remove(db_session, acteur, allowed_email_repository.get_by_email(db_session, "a@club.fr"))
    db_session.commit()
    assert user.is_active is False

    with pytest.raises(LoginError) as refus:
        provisioning.resolve_user(db_session, _identity(email="b@gmail.com"))
    assert refus.value.code == "account_not_allowed"


def test_une_adresse_autorisee_peut_remplacer_une_autre_adresse_autorisee(db_session, autoriser):
    """La règle ne fige que le passage d'une adresse inscrite à une adresse hors liste."""
    autoriser("nouvelle@club.fr")
    user = provisioning.resolve_user(db_session, _identity())
    provisioning.resolve_user(db_session, _identity(email="nouvelle@club.fr"))

    assert user.email == "nouvelle@club.fr"
