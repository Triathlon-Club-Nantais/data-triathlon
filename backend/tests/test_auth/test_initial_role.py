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


# --- Le choix du rôle est gardé, l'application ne l'est pas ------------------


def test_choisir_un_role_qu_on_ne_porte_pas_rend_403(
    client, ouvrir_session, db_session, organisation
):
    """La non-amplification (FR-011) s'applique **au moment du choix**."""
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
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
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)
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
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

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
    ouvrir_session(P.ALLOWED_EMAILS_MANAGE)

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
