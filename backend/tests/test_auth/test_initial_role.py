"""Le rôle porté par l'autorisation, posé à la naissance du compte (#239).

**Le geste d'administration était coupé en deux par un événement que
l'administrateur ne contrôle pas** : autoriser une adresse, puis *attendre* que
la personne se connecte, puis retourner sur un autre écran lui donner un rôle.
Entre les deux, elle était connectée sans rien.

Le rôle vit donc sur l'autorisation, et s'applique **à la création** du compte —
jamais à une reconnexion, jamais à une réactivation : ce serait réécrire les
rôles d'un compte vivant depuis une table qui n'identifie personne.

Le contrôle porte sur le **choix**, où il y a un acteur, et non sur
l'application, où il n'y en a pas — c'est la même asymétrie que `grant-role`.
"""
import pytest

from app.core.permissions import P
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.repositories import allowed_email_repository, user_role_repository
from app.services.auth import allowed_emails, flow, state

from .conftest import ADRESSE_AUTORISEE


def _connexion(db, doublure):
    """Le parcours nominal de la doublure, jusqu'au compte créé."""
    _, jeton_etat = flow.start_login(doublure.slug)
    charge = state.read(jeton_etat)
    _, user = flow.complete_login(
        db,
        provider_slug=doublure.slug,
        state_token=jeton_etat,
        state_param=charge.state,
        code="code-de-retour",
        error=None,
    )
    db.commit()
    return user


def _roles_de(db, user, organisation):
    return [
        attribution.role.slug
        for attribution in user_role_repository.list_for_user(
            db, user.id, organisation_id=organisation.id
        )
    ]


@pytest.fixture
def benevole(db_session, organisation):
    """Un rôle ordinaire, sans pouvoir : ce qu'on donne à qui arrive."""
    role = Role(slug="benevole", name="Bénévole", organisation_id=organisation.id)
    db_session.add(role)
    db_session.commit()
    return role


def test_le_role_de_l_autorisation_est_pose_a_la_creation_du_compte(
    db_session, doublure, organisation, benevole
):
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.commit()

    user = _connexion(db_session, doublure)

    assert _roles_de(db_session, user, organisation) == ["benevole"]


def test_sans_role_porte_le_compte_nait_sans_rien(
    db_session, doublure, organisation
):
    """L'état d'avant reste possible : le rôle initial est facultatif."""
    user = _connexion(db_session, doublure)

    assert _roles_de(db_session, user, organisation) == []


def test_une_reconnexion_ne_repose_pas_le_role(
    db_session, doublure, organisation, benevole
):
    """Sinon retirer un rôle à quelqu'un serait défait par sa prochaine
    connexion, sans que rien ne le dise."""
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.commit()
    user = _connexion(db_session, doublure)
    user_role_repository.revoke(
        db_session, user_id=user.id, role_id=benevole.id, organisation_id=organisation.id
    )
    db_session.commit()

    _connexion(db_session, doublure)

    assert _roles_de(db_session, user, organisation) == []


def test_une_seconde_identite_sur_la_meme_adresse_ne_recoit_rien(
    db_session, doublure, organisation, benevole
):
    """**Le rôle se consomme.** Sinon il est apparié par *adresse*, sans borne.

    Toute identité externe inconnue crée un nouvel utilisateur, « même si
    l'adresse est déjà en base » (FR-003) — c'est ce qui ferme la prise de
    contrôle par pré-inscription. Un rôle qui resterait posé rouvrirait ce même
    appariement sur un chemin qui, lui, **accorde du pouvoir** : chaque nouvelle
    identité portant l'adresse redeviendrait ce que la première était, y compris
    après une révocation.
    """
    from app.services.auth.idp.base import ExternalIdentity

    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.commit()
    premier = _connexion(db_session, doublure)
    doublure.identite = ExternalIdentity(
        provider=doublure.slug,
        subject="doublure-2",
        email=ADRESSE_AUTORISEE,
        email_verified=True,
        display_name="Second",
    )

    second = _connexion(db_session, doublure)

    assert second.id != premier.id, "FR-003 : deux identités, deux comptes"
    assert _roles_de(db_session, premier, organisation) == ["benevole"]
    assert _roles_de(db_session, second, organisation) == []


def test_le_role_applique_est_leve_de_l_autorisation(
    db_session, doublure, benevole
):
    """Corollaire visible du précédent, et le seul retour honnête à l'écran :
    « — » dit *appliqué*, le rôle est désormais sur le compte."""
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.commit()

    _connexion(db_session, doublure)

    assert (
        allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE).role_id
        is None
    )


# --- Le choix du rôle est gardé, l'application ne l'est pas ------------------


def test_choisir_un_role_qu_on_ne_porte_pas_rend_403(
    client, ouvrir_session, db_session, organisation
):
    """La non-amplification (FR-011) s'applique **au moment du choix**."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN)
    role = Role(slug="archivist", name="Archiviste")
    role.permissions.append(RolePermission(permission_code=P.PARTICIPATIONS_DELETE.code))
    db_session.add(role)
    db_session.commit()

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": role.id},
    )

    assert reponse.status_code == 403


def test_choisir_le_role_superutilisateur_sans_l_etre_rend_403(
    client, ouvrir_session, db_session
):
    """FR-010 — sinon la voie d'escalade fermée sur l'attribution rouvre ici."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN)
    role = Role(slug="root", name="Administrateur", is_superuser=True)
    db_session.add(role)
    db_session.commit()

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": role.id},
    )

    assert reponse.status_code == 403


def test_choisir_un_role_qu_on_porte_aboutit_et_se_relit(
    client, ouvrir_session, db_session, organisation, benevole
):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN)

    creation = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": benevole.id},
    )

    assert creation.status_code == 201
    assert creation.json()["role"]["slug"] == "benevole"
    inscrites = client.get("/api/v1/admin/allowed-emails").json()
    assert [e["role"]["slug"] for e in inscrites if e["email"] == "nouveau@exemple.fr"] == [
        "benevole"
    ]


def test_un_role_inconnu_rend_404(client, ouvrir_session):
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN)

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": 9999},
    )

    assert reponse.status_code == 404


def test_supprimer_un_role_pose_en_role_initial_rend_409(
    client, ouvrir_session, db_session, benevole
):
    """Même refus que pour un porteur : pas de cascade, on nomme la raison.

    Sans lui, la clé étrangère céderait en PostgreSQL et serait **inerte** en
    SQLite — deux comportements pour un même geste.
    """
    ouvrir_session(P.ROLES_WRITE, superutilisateur=True)
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.commit()

    reponse = client.delete(f"/api/v1/admin/roles/{benevole.id}")

    assert reponse.status_code == 409
    assert "adresse" in reponse.json()["detail"].lower()


def test_le_role_disparu_ne_bloque_pas_la_connexion(
    db_session, doublure, organisation, benevole
):
    """La FK est inerte en SQLite : l'état est atteignable, et une connexion
    refusée pour cette raison serait indiagnosticable côté visiteur."""
    entree = allowed_email_repository.get_by_email(db_session, ADRESSE_AUTORISEE)
    allowed_email_repository.set_initial_role(db_session, entree, role_id=benevole.id)
    db_session.delete(benevole)
    db_session.commit()

    user = _connexion(db_session, doublure)

    assert _roles_de(db_session, user, organisation) == []


def test_le_service_expose_le_choix_a_la_cli_sans_acteur(db_session, benevole):
    """`allow-email` n'a pas d'acteur : le service doit rester appelable."""
    entree, creee, _ = allowed_emails.add(
        db_session, None, email="cli@exemple.fr", role_id=benevole.id
    )

    assert creee is True
    assert entree.role_id == benevole.id


# --- Lever un rôle posé -----------------------------------------------------


def test_reinscrire_sans_role_leve_celui_qui_etait_pose(
    client, ouvrir_session, db_session, benevole
):
    """« Aucun » est un choix, pas une absence de choix.

    L'écran l'offre, et sans ce chemin le rôle se collait à l'adresse : plus
    aucun moyen de le lever, et le 409 de `delete_role` réclamait un geste qui
    n'existait pas — le rôle en devenait indélébile.
    """
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN)
    client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": benevole.id},
    )

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": None},
    )

    assert reponse.status_code == 201
    assert reponse.json()["role"] is None
    assert (
        allowed_email_repository.get_by_email(db_session, "nouveau@exemple.fr").role_id
        is None
    )


def test_la_cli_qui_ne_nomme_aucun_role_ne_leve_rien(db_session, benevole):
    """`allow-email` réautorise une adresse ; elle ne se prononce pas sur le rôle.

    Sans cette distinction, rouvrir un accès depuis le serveur effacerait en
    silence un choix fait à l'écran — « je n'en parle pas » n'est pas « aucun ».
    """
    allowed_emails.add(db_session, None, email="cli@exemple.fr", role_id=benevole.id)

    entree, _, _ = allowed_emails.add(db_session, None, email="cli@exemple.fr")

    assert entree.role_id == benevole.id


# --- Le troisième chemin d'attribution porte les mêmes gardes que le premier -


def test_choisir_un_role_exige_le_pouvoir_de_les_attribuer(
    client, ouvrir_session, benevole
):
    """Donner un rôle est `roles:assign`, quel que soit le guichet.

    Sans cette garde, `allowed_emails:manage` — un pouvoir unique dont le
    plafond assumé était « fermer n'importe quel compte » — vaudrait aussi
    « distribuer des rôles à tout compte à naître ». La non-amplification borne
    ce qu'on donne, elle ne dit pas qu'on a le droit de donner.
    """
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": benevole.id},
    )

    assert reponse.status_code == 403


def test_un_role_inconnu_rend_403_a_qui_n_attribue_pas(client, ouvrir_session):
    """403 **avant** 404 : sinon le couple 404/201 balaie le catalogue.

    Un porteur d'`allowed_emails:manage` seul — qui n'a même pas `roles:read` —
    apprendrait par balayage d'identifiants quels rôles existent, leur nom, leur
    slug et leur portée, le corps du 201 les rendant.
    """
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": 9999},
    )

    assert reponse.status_code == 403


def test_autoriser_sans_nommer_de_role_n_exige_rien_de_plus(client, ouvrir_session):
    """Le pouvoir supplémentaire ne s'exige que si un rôle est nommé."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

    reponse = client.post(
        "/api/v1/admin/allowed-emails", json={"email": "nouveau@exemple.fr"}
    )

    assert reponse.status_code == 201


def test_un_role_d_une_autre_organisation_est_refuse_au_choix(
    client, ouvrir_session, db_session
):
    """FR-008 — refusé là où il se choisit, pas ignoré là où il s'applique.

    `grant_role` porte ce contrôle depuis #115 ; le chemin du rôle initial est
    le **troisième** écrivain de `user_roles`, et il avait été ajouté avec deux
    des trois gardes du premier.
    """
    from app.models.organisation import Organisation

    ouvrir_session(P.ALLOWED_EMAILS_MANAGE, P.ROLES_ASSIGN, superutilisateur=True)
    autre = Organisation(slug="autre-club", name="Autre club")
    db_session.add(autre)
    db_session.flush()
    role = Role(slug="ailleurs", name="Ailleurs", organisation_id=autre.id)
    db_session.add(role)
    db_session.commit()

    reponse = client.post(
        "/api/v1/admin/allowed-emails",
        json={"email": "nouveau@exemple.fr", "role_id": role.id},
    )

    assert reponse.status_code == 422
