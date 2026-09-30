"""Les gestes sur les droits d'accès laissent une trace durable (#935).

Rôles, groupes, liste d'autorisation, révocation de sessions, fournisseur
signalé traité : ils ne laissaient qu'un `logger.info`, perdu à la rétention des
logs Render. Chacun écrit maintenant une ligne `admin_action_log` dans la même
transaction que son effet, et un geste refusé n'en écrit aucune.
"""
from app.core.permissions import P
from app.models.admin_action_log import AdminActionLog
from app.repositories import pending_provider_repository, role_repository, user_repository


def _journal(db_session) -> list[tuple[str, str]]:
    db_session.expire_all()
    return [
        (ligne.action, ligne.entity_type)
        for ligne in db_session.query(AdminActionLog).order_by(AdminActionLog.id)
    ]


def _dernier(db_session) -> AdminActionLog:
    db_session.expire_all()
    return db_session.query(AdminActionLog).order_by(AdminActionLog.id.desc()).first()


def test_role_lifecycle_is_recorded(client, ouvrir_session, db_session):
    acteur = ouvrir_session(superutilisateur=True)

    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": [P.QUALITY_OVERRIDE.code]},
    ).json()
    creation = _dernier(db_session)
    client.patch(f"/api/v1/admin/roles/{role['id']}", json={"permissions": []})
    modification = _dernier(db_session)
    client.delete(f"/api/v1/admin/roles/{role['id']}")

    assert _journal(db_session) == [
        ("role.create", "role"), ("role.update", "role"), ("role.delete", "role"),
    ]
    assert creation.user_id == acteur.id
    assert creation.entity_id == role["id"]
    assert creation.payload["slug"] == "archivist"
    assert creation.payload["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert modification.payload["before"]["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert modification.payload["after"]["permissions"] == []


def test_granting_and_revoking_a_role_are_recorded(client, ouvrir_session, db_session):
    ouvrir_session(superutilisateur=True)
    cible = user_repository.create(db_session, email="cible@exemple.fr", display_name="Cible")
    role = role_repository.create(db_session, slug="lecteur", name="Lecteur")
    db_session.commit()

    client.post(f"/api/v1/admin/users/{cible.id}/roles", json={"role_id": role.id})
    attribution = _dernier(db_session)
    client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role.id}")

    assert _journal(db_session) == [("role.grant", "user"), ("role.revoke", "user")]
    assert attribution.entity_id == cible.id
    assert attribution.payload["role"] == "lecteur"


def test_a_refused_grant_writes_nothing(client, ouvrir_session, db_session):
    """403 : la non-amplification refuse de donner un rôle superutilisateur."""
    ouvrir_session(P.ROLES_ASSIGN)
    cible = user_repository.create(db_session, email="cible@exemple.fr", display_name="Cible")
    role = role_repository.create(db_session, slug="tout", name="Tout", is_superuser=True)
    db_session.commit()

    reponse = client.post(f"/api/v1/admin/users/{cible.id}/roles", json={"role_id": role.id})

    assert reponse.status_code == 403
    assert _journal(db_session) == []


def test_group_lifecycle_and_membership_are_recorded(client, ouvrir_session, db_session):
    ouvrir_session(superutilisateur=True)
    membre = user_repository.create(db_session, email="membre@exemple.fr", display_name="Membre")
    db_session.commit()

    groupe = client.post("/api/v1/admin/groups", json={"slug": "bureau", "name": "Bureau"}).json()
    client.patch(f"/api/v1/admin/groups/{groupe['id']}", json={"name": "Le bureau"})
    client.post(f"/api/v1/admin/groups/{groupe['id']}/members", json={"user_id": membre.id})
    ajout = _dernier(db_session)
    client.delete(f"/api/v1/admin/groups/{groupe['id']}/members/{membre.id}")
    client.delete(f"/api/v1/admin/groups/{groupe['id']}")

    assert _journal(db_session) == [
        ("group.create", "group"),
        ("group.update", "group"),
        ("group.member_add", "group"),
        ("group.member_remove", "group"),
        ("group.delete", "group"),
    ]
    assert ajout.payload["user_id"] == membre.id


def test_allow_list_changes_are_recorded(client, ouvrir_session, db_session):
    ouvrir_session(superutilisateur=True)

    entree = client.post("/api/v1/admin/allowed-emails", json={"email": "nouveau@exemple.fr"}).json()
    ajout = _dernier(db_session)
    client.delete(f"/api/v1/admin/allowed-emails/{entree['id']}")

    assert _journal(db_session) == [
        ("allowed_email.add", "allowed_email"), ("allowed_email.remove", "allowed_email"),
    ]
    assert ajout.payload["email"] == "nouveau@exemple.fr"


def test_removing_the_last_admin_address_writes_nothing(client, ouvrir_session, db_session, autoriser):
    """409 : l'invariant du dernier administrateur refuse le retrait."""
    from app.repositories import allowed_email_repository

    ouvrir_session(superutilisateur=True, email="seul-admin@exemple.fr")
    autoriser("seul-admin@exemple.fr")
    db_session.commit()
    entree = allowed_email_repository.get_by_email(db_session, "seul-admin@exemple.fr")

    reponse = client.delete(f"/api/v1/admin/allowed-emails/{entree.id}")

    assert reponse.status_code == 409
    assert _journal(db_session) == []


def test_session_revocation_is_recorded_even_when_it_closes_the_author(
    client, ouvrir_session, db_session
):
    acteur = ouvrir_session(P.SESSIONS_REVOKE)

    client.post("/api/v1/admin/sessions/revoke")

    ligne = _dernier(db_session)
    assert (ligne.action, ligne.user_id) == ("sessions.revoke", acteur.id)
    assert ligne.payload["scope"] == "all"
    assert ligne.payload["sessions"] >= 1


def test_handling_a_pending_provider_is_recorded(client, ouvrir_session, db_session):
    ouvrir_session(P.PENDING_PROVIDERS_HANDLE)
    entree = pending_provider_repository.create(db_session, url="https://inconnu.test/resultats")
    db_session.commit()

    client.delete(f"/api/v1/admin/pending-providers/{entree.id}")

    ligne = _dernier(db_session)
    assert (ligne.action, ligne.entity_type, ligne.entity_id) == (
        "pending_provider.handle", "pending_provider", entree.id,
    )
