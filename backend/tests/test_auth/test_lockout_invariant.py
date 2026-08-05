"""Ne jamais fermer la porte de l'intérieur (#115, FR-032, SC-007).

Aucune séquence d'opérations effectuée **depuis l'application** ne doit laisser
une organisation sans administrateur actif. L'édition à chaud multiplie les
façons de se verrouiller — retirer une attribution, supprimer le rôle, décocher
`is_superuser` —, et chaque nouvelle façon d'éditer les droits en ouvrira une
quatrième.

On ne garde donc pas les chemins, on garde **l'état d'arrivée**, une seule fois.
"""
import pytest

from app.models.role import Role
from app.repositories import user_role_repository


@pytest.fixture
def role_admin(db_session) -> Role:
    role = Role(
        slug="admin", name="Administrateur", is_system=True, is_superuser=True
    )
    db_session.add(role)
    db_session.flush()
    return role


def _nommer(db_session, user, role, organisation):
    user_role_repository.grant(
        db_session,
        user_id=user.id,
        role_id=role.id,
        organisation_id=organisation.id,
    )
    db_session.commit()


@pytest.fixture
def seul_administrateur(client, db_session, ouvrir_session, role_admin, organisation):
    """Une installation à **un** administrateur : la session ouverte est la sienne."""
    user = ouvrir_session()
    _nommer(db_session, user, role_admin, organisation)
    return user


@pytest.fixture
def second_administrateur(db_session, ouvrir_session, role_admin, organisation):
    user = ouvrir_session(pose_le_cookie=False)
    _nommer(db_session, user, role_admin, organisation)
    return user


# --- Avec un unique administrateur : les trois chemins sont refusés ----------


def test_retirer_sa_propre_attribution_rend_409(
    client, seul_administrateur, role_admin
):
    reponse = client.delete(
        f"/api/v1/admin/users/{seul_administrateur.id}/roles/{role_admin.id}"
    )

    assert reponse.status_code == 409
    assert "administrateur" in reponse.json()["detail"]


def test_supprimer_le_role_qui_rend_administrateur_rend_409(
    client, seul_administrateur, role_admin
):
    """Deux refus se disputent ce cas, et **le premier suffit** : le rôle est
    encore porté (FR-007). L'invariant reste le filet du cas où il ne le serait
    plus."""
    reponse = client.delete(f"/api/v1/admin/roles/{role_admin.id}")

    assert reponse.status_code == 409


def test_decocher_is_superuser_sur_ce_role_rend_409(
    client, seul_administrateur, role_admin
):
    """Le chemin le plus discret : la table `user_roles` ne bouge pas d'une ligne.

    C'est exactement pourquoi l'invariant juge l'**état d'arrivée** et non
    l'opération : rien dans ce `PATCH` ne ressemble à un retrait de droits.
    """
    reponse = client.patch(
        f"/api/v1/admin/roles/{role_admin.id}", json={"is_superuser": False}
    )

    assert reponse.status_code == 409


def test_le_refus_laisse_l_etat_intact(
    client, db_session, seul_administrateur, role_admin, organisation
):
    """Un 409 qui aurait déjà écrit serait pire qu'un 200."""
    client.delete(f"/api/v1/admin/users/{seul_administrateur.id}/roles/{role_admin.id}")
    db_session.rollback()

    from app.services.auth import authorization

    assert authorization.count_active_superusers(db_session, organisation.id) == 1


# --- Avec deux administrateurs : les trois aboutissent ----------------------


def test_avec_deux_administrateurs_le_retrait_aboutit(
    client, seul_administrateur, second_administrateur, role_admin
):
    reponse = client.delete(
        f"/api/v1/admin/users/{seul_administrateur.id}/roles/{role_admin.id}"
    )

    assert reponse.status_code == 204


def test_avec_deux_administrateurs_decocher_is_superuser_aboutit(
    client, db_session, seul_administrateur, ouvrir_session, organisation
):
    """Le second porte un **autre** rôle superutilisateur : décocher le premier
    ne verrouille donc rien."""
    autre = Role(slug="root", name="Racine", is_superuser=True)
    db_session.add(autre)
    db_session.flush()
    _nommer(db_session, ouvrir_session(pose_le_cookie=False), autre, organisation)
    admin = db_session.query(Role).filter_by(slug="admin").one()

    reponse = client.patch(
        f"/api/v1/admin/roles/{admin.id}", json={"is_superuser": False}
    )

    assert reponse.status_code == 200


def test_un_administrateur_retire_a_un_pair_son_caractere_d_administration(
    client, seul_administrateur, second_administrateur, role_admin
):
    """FR-010 — **poser et retirer sont la même règle**.

    Un 403 ici serait un garde défensif de trop, et il enfermerait l'installation
    dans une composition qu'on ne pourrait plus défaire : le pair nommé par
    erreur le resterait à jamais.
    """
    reponse = client.delete(
        f"/api/v1/admin/users/{second_administrateur.id}/roles/{role_admin.id}"
    )

    assert reponse.status_code == 204


# --- Un compte désactivé ne compte pas -------------------------------------


def test_un_administrateur_desactive_ne_compte_pas_comme_actif(
    client, db_session, seul_administrateur, second_administrateur, role_admin
):
    """La table `user_roles` en montre deux, et il n'y en a qu'un.

    « Actifs » au sens de #114 : les sessions d'un compte désactivé sont déjà
    tombées, l'invariant à trois conditions étant une jointure. Compter les
    lignes plutôt que les comptes laisserait une installation verrouillée
    derrière quelqu'un qui ne peut plus se connecter.
    """
    second_administrateur.is_active = False
    db_session.commit()

    reponse = client.delete(
        f"/api/v1/admin/users/{seul_administrateur.id}/roles/{role_admin.id}"
    )

    assert reponse.status_code == 409


def test_deux_roles_superutilisateur_sur_la_meme_personne_ne_font_qu_un_admin(
    client, db_session, seul_administrateur, organisation
):
    """Le comptage porte sur des **utilisateurs distincts**, pas sur des lignes."""
    second_role = Role(slug="root", name="Racine", is_superuser=True)
    db_session.add(second_role)
    db_session.flush()
    _nommer(db_session, seul_administrateur, second_role, organisation)
    admin = db_session.query(Role).filter_by(slug="admin").one()

    reponse = client.delete(
        f"/api/v1/admin/users/{seul_administrateur.id}/roles/{second_role.id}"
    )

    assert reponse.status_code == 204, "il lui reste `admin`"
    assert (
        client.delete(
            f"/api/v1/admin/users/{seul_administrateur.id}/roles/{admin.id}"
        ).status_code
        == 409
    ), "celui-là est le dernier"
