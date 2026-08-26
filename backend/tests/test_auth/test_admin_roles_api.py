"""Composer un rôle à chaud : les sept ressources de `contracts/admin-api.md`.

Ce fichier tient le **parcours nominal** (FR-004) et les refus (FR-006 à FR-012).
La non-amplification a son propre fichier ; les pouvoirs périmés aussi.
"""
from app.core.permissions import P
from app.models.organisation import Organisation
from app.models.role import Role


def test_l_inventaire_des_pouvoirs_est_groupe_par_fonctionnalite(
    client, ouvrir_session
):
    ouvrir_session(P.ROLES_READ)

    reponse = client.get("/api/v1/admin/permissions")

    assert reponse.status_code == 200
    groupes = reponse.json()
    assert groupes
    codes = [
        pouvoir["code"] for groupe in groupes for pouvoir in groupe["permissions"]
    ]
    assert "quality:override" in codes
    premier = groupes[0]["permissions"][0]
    assert {"code", "label", "description"} <= set(premier)
    assert premier["label"] != premier["code"], "le libellé doit être du français"


def test_l_inventaire_exige_roles_read(client, ouvrir_session):
    """FR-003 — et ce n'est pas une question de secret : les codes sont publics.

    C'est que cet inventaire n'a **pas d'autre lecteur** : son seul usage est de
    composer un rôle. Qui veut connaître *ses* pouvoirs lit `GET /auth/me`.
    """
    ouvrir_session()

    assert client.get("/api/v1/admin/permissions").status_code == 403


def test_creer_lire_modifier_et_supprimer_un_role(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)

    creation = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "archivist",
            "name": "Archiviste",
            "description": "Range les vieilles épreuves.",
            "permissions": [P.QUALITY_OVERRIDE.code],
        },
    )
    assert creation.status_code == 201
    role = creation.json()
    assert role["slug"] == "archivist"
    assert role["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert role["stale_permissions"] == []
    assert role["holders"] == 0
    assert role["is_system"] is False

    detail = client.get(f"/api/v1/admin/roles/{role['id']}")
    assert detail.status_code == 200
    assert detail.json() == role

    liste = client.get("/api/v1/admin/roles")
    assert liste.status_code == 200
    assert role["id"] in [ligne["id"] for ligne in liste.json()]

    modification = client.patch(
        f"/api/v1/admin/roles/{role['id']}",
        json={"name": "Archiviste en chef", "permissions": []},
    )
    assert modification.status_code == 200
    assert modification.json()["name"] == "Archiviste en chef"
    assert modification.json()["permissions"] == []

    suppression = client.delete(f"/api/v1/admin/roles/{role['id']}")
    assert suppression.status_code == 204
    assert client.get(f"/api/v1/admin/roles/{role['id']}").status_code == 404


def test_attribuer_puis_retirer_un_role(client, ouvrir_session, db_session, organisation):
    exploitant = ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()

    attribution = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": role["id"], "organisation_id": organisation.id},
    )

    assert attribution.status_code == 201
    assert [r["slug"] for r in attribution.json()["roles"]] == ["archivist"]
    assert exploitant.id != cible.id

    retrait = client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role['id']}")

    assert retrait.status_code == 204
    assert client.get(f"/api/v1/admin/roles/{role['id']}").json()["holders"] == 0


def test_reattribuer_un_role_deja_porte_est_un_succes(
    client, ouvrir_session, organisation
):
    """FR-012 — edge case des deux exploitants simultanés.

    Jamais une violation d'unicité remontée en 500 : c'est la contrainte qui rend
    l'opération idempotente, et l'API le rend visible.
    """
    ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()
    corps = {"role_id": role["id"], "organisation_id": organisation.id}

    premiere = client.post(f"/api/v1/admin/users/{cible.id}/roles", json=corps)
    seconde = client.post(f"/api/v1/admin/users/{cible.id}/roles", json=corps)

    assert (premiere.status_code, seconde.status_code) == (201, 201)
    assert client.get(f"/api/v1/admin/roles/{role['id']}").json()["holders"] == 1


def test_retirer_un_role_non_porte_est_un_succes(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()

    retrait = client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role['id']}")

    assert retrait.status_code == 204


def test_renommer_un_role_ne_perd_aucune_attribution(
    client, ouvrir_session, organisation
):
    """FR-005 — **la** justification de `role_id` plutôt que `role` en chaîne.

    Avec une chaîne, un renommage aurait été une migration de données ; ici il
    est gratuit, et deux porteurs le restent.
    """
    ouvrir_session(superutilisateur=True)
    premier = ouvrir_session(pose_le_cookie=False)
    second = ouvrir_session(pose_le_cookie=False)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()
    for cible in (premier, second):
        client.post(
            f"/api/v1/admin/users/{cible.id}/roles",
            json={"role_id": role["id"], "organisation_id": organisation.id},
        )

    client.patch(f"/api/v1/admin/roles/{role['id']}", json={"name": "Conservateur"})

    apres = client.get(f"/api/v1/admin/roles/{role['id']}").json()
    assert apres["name"] == "Conservateur"
    assert apres["slug"] == "archivist"
    assert apres["holders"] == 2


def test_lister_les_utilisateurs_avec_leurs_roles(client, ouvrir_session, organisation):
    ouvrir_session(P.USERS_READ, P.ROLES_READ)

    reponse = client.get("/api/v1/admin/users")

    assert reponse.status_code == 200
    lignes = reponse.json()
    assert lignes
    premiere = lignes[0]
    assert {"id", "email", "display_name", "is_active", "roles", "created_at"} <= set(
        premiere
    )


def test_lister_les_utilisateurs_exige_users_read(client, ouvrir_session):
    ouvrir_session(P.ROLES_READ)

    assert client.get("/api/v1/admin/users").status_code == 403


# --- Refus (T035) -----------------------------------------------------------


def test_soumettre_un_slug_a_patch_rend_422(client, ouvrir_session):
    """Le slug est **immuable** : c'est le seul nom qui traverse une frontière.

    `grant-role --role`, le semis de la migration : le renommer casserait les
    deux, en silence.
    """
    ouvrir_session(superutilisateur=True)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()

    reponse = client.patch(
        f"/api/v1/admin/roles/{role['id']}", json={"slug": "conservateur"}
    )

    assert reponse.status_code == 422


def test_un_code_hors_catalogue_soumis_rend_422(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)

    creation = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": ["courses:burn"]},
    )

    assert creation.status_code == 422


def test_un_slug_deja_pris_dans_la_meme_portee_rend_409(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)
    corps = {"slug": "archivist", "name": "Archiviste", "permissions": []}
    client.post("/api/v1/admin/roles", json=corps)

    assert client.post("/api/v1/admin/roles", json=corps).status_code == 409


def test_une_collision_de_slug_sous_concurrence_rend_409_et_non_500(
    client, ouvrir_session, monkeypatch
):
    """Le chemin que la lecture préalable **ne** couvre pas, et qu'elle masquait.

    `create_role` enveloppait un `db.flush()` d'après-coup, alors que
    `role_repository.create` flushe lui-même : l'`IntegrityError` était levée
    **avant** d'entrer dans le `try`, et remontait nue — 500, transaction
    invalidée, là où le contrat promet 409. Le test précédent ne pouvait pas le
    voir : il passe par la lecture préalable, jamais par la contrainte.

    Défaut trouvé en revue de #197, dont le service jumeau portait le même
    (`services/auth/groups.py`). La lecture est ici neutralisée pour simuler la
    course, ce qu'aucun test concurrent ne saurait rendre déterministe.
    """
    from app.repositories import role_repository

    ouvrir_session(superutilisateur=True)
    corps = {"slug": "archivist", "name": "Archiviste", "permissions": []}
    client.post("/api/v1/admin/roles", json=corps)
    monkeypatch.setattr(role_repository, "find_in_scope", lambda *a, **k: None)

    assert client.post("/api/v1/admin/roles", json=corps).status_code == 409


def test_supprimer_un_role_systeme_rend_409(client, ouvrir_session, db_session):
    ouvrir_session(superutilisateur=True)
    livre = Role(slug="validator", name="Validateur", is_system=True)
    db_session.add(livre)
    db_session.commit()

    reponse = client.delete(f"/api/v1/admin/roles/{livre.id}")

    assert reponse.status_code == 409
    assert "livré" in reponse.json()["detail"]


def test_un_role_systeme_accepte_pourtant_d_etre_recompose(
    client, ouvrir_session, db_session
):
    """FR-006, la moitié que le refus fait oublier : **livré ne veut pas dire figé**.

    Un rôle semé doit rester renommable et recomposable — c'est même la raison
    pour laquelle sa composition est en base et non dans le code.
    """
    ouvrir_session(superutilisateur=True)
    livre = Role(slug="validator", name="Validateur", is_system=True)
    db_session.add(livre)
    db_session.commit()

    reponse = client.patch(
        f"/api/v1/admin/roles/{livre.id}",
        json={
            "name": "Juge de fiabilité",
            "description": "Modifié à chaud.",
            "permissions": [P.QUALITY_OVERRIDE.code],
        },
    )

    assert reponse.status_code == 200
    assert reponse.json()["name"] == "Juge de fiabilité"
    assert reponse.json()["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert reponse.json()["is_system"] is True


def test_supprimer_un_role_encore_attribue_rend_409_en_nommant_les_porteurs(
    client, ouvrir_session, organisation
):
    """FR-007 — le nombre est **dans le message**.

    « Ce rôle est porté par 2 utilisateurs » se corrige ; « conflit » ne se
    corrige pas. Et pas de cascade : dépouiller silencieusement deux personnes
    est exactement ce qu'on rend explicite.
    """
    ouvrir_session(superutilisateur=True)
    premier = ouvrir_session(pose_le_cookie=False)
    second = ouvrir_session(pose_le_cookie=False)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()
    for cible in (premier, second):
        client.post(
            f"/api/v1/admin/users/{cible.id}/roles",
            json={"role_id": role["id"], "organisation_id": organisation.id},
        )

    reponse = client.delete(f"/api/v1/admin/roles/{role['id']}")

    assert reponse.status_code == 409
    assert "2" in reponse.json()["detail"]


def test_attribuer_un_role_d_une_autre_organisation_rend_422(
    client, ouvrir_session, db_session, organisation
):
    """FR-008 — la règle qu'aucun SQL portable n'exprime : elle croise deux tables."""
    ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)
    autre = Organisation(slug="autre", name="Autre club")
    db_session.add(autre)
    db_session.flush()
    etranger = Role(slug="archivist", name="Archiviste", organisation_id=autre.id)
    db_session.add(etranger)
    db_session.commit()

    reponse = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": etranger.id, "organisation_id": organisation.id},
    )

    assert reponse.status_code == 422


def test_attribuer_a_un_utilisateur_inconnu_rend_404(
    client, ouvrir_session, organisation
):
    ouvrir_session(superutilisateur=True)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()

    reponse = client.post(
        "/api/v1/admin/users/9999/roles",
        json={"role_id": role["id"], "organisation_id": organisation.id},
    )

    assert reponse.status_code == 404


def test_attribuer_un_role_inconnu_rend_404(client, ouvrir_session, organisation):
    ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)

    reponse = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": 9999, "organisation_id": organisation.id},
    )

    assert reponse.status_code == 404


def test_deux_roles_globaux_de_meme_slug_rendent_409_et_non_500(client, ouvrir_session):
    """L'index partiel refuse en base ; l'API doit le traduire, pas le laisser fuiter."""
    ouvrir_session(superutilisateur=True)
    corps = {"slug": "archivist", "name": "Archiviste", "permissions": []}
    client.post("/api/v1/admin/roles", json=corps)

    reponse = client.post("/api/v1/admin/roles", json={**corps, "name": "Autre nom"})

    assert reponse.status_code == 409


def test_toutes_les_ressources_de_roles_exigent_leur_pouvoir(client, ouvrir_session):
    """Chacune porte sa garde **individuellement** (FR-017, FR-018)."""
    ouvrir_session()

    refus = [
        client.get("/api/v1/admin/roles"),
        client.post("/api/v1/admin/roles", json={"slug": "x", "name": "X"}),
        client.patch("/api/v1/admin/roles/1", json={"name": "X"}),
        client.delete("/api/v1/admin/roles/1"),
        client.get("/api/v1/admin/users"),
        client.post("/api/v1/admin/users/1/roles", json={"role_id": 1}),
        client.delete("/api/v1/admin/users/1/roles/1"),
    ]

    assert [reponse.status_code for reponse in refus] == [403] * 7


def test_lister_les_roles_rend_le_bon_nombre_de_porteurs_par_role(
    client, ouvrir_session, db_session, organisation
):
    """#625 — `holders` venait d'un `count_holders` par rôle listé ; le passage
    à une requête agrégée ne doit rien changer au résultat, seulement à son coût.
    """
    from app.repositories import role_repository, user_role_repository

    ouvrir_session(superutilisateur=True)
    solo = role_repository.create(db_session, slug="solo", name="Solo")
    duo = role_repository.create(db_session, slug="duo", name="Duo")
    role_repository.create(db_session, slug="orphelin", name="Orphelin")
    db_session.flush()
    for slug_role, nb_porteurs in ((solo, 1), (duo, 2)):
        for i in range(nb_porteurs):
            # `pose_le_cookie=False` : la session active pour la requête finale
            # doit rester celle du superutilisateur ouverte plus haut.
            porteur = ouvrir_session(
                email=f"{slug_role.slug}-{i}@exemple.fr", pose_le_cookie=False
            )
            user_role_repository.grant(
                db_session,
                user_id=porteur.id,
                role_id=slug_role.id,
                organisation_id=organisation.id,
            )
    db_session.commit()

    liste = client.get("/api/v1/admin/roles")
    assert liste.status_code == 200
    porteurs_par_slug = {ligne["slug"]: ligne["holders"] for ligne in liste.json()}
    assert porteurs_par_slug["solo"] == 1
    assert porteurs_par_slug["duo"] == 2
    assert porteurs_par_slug["orphelin"] == 0


def test_lister_les_roles_tient_en_un_nombre_de_requetes_fixe_quel_que_soit_le_nombre_de_roles(
    client, ouvrir_session, db_session
):
    """#625 — un `count_holders` et un lazy-load de `.permissions` par rôle
    faisaient scaler le coût de cette liste avec le nombre de rôles."""
    from sqlalchemy import event

    from app.repositories import role_repository

    ouvrir_session(superutilisateur=True)
    for i in range(5):
        # `r-N`, jamais `role-N` : `ouvrir_session` nomme déjà son propre rôle
        # `role-1` (compteur d'appels de la fixture), collision de slug sinon.
        role_repository.create(db_session, slug=f"r-{i}", name=f"Rôle {i}")
    db_session.commit()
    db_session.expire_all()

    requetes = []

    def _mouchard(conn, cursor, statement, *reste):
        requetes.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _mouchard)
    try:
        reponse = client.get("/api/v1/admin/roles")
    finally:
        event.remove(engine, "before_cursor_execute", _mouchard)

    assert reponse.status_code == 200
    # Fixe, quel que soit le nombre de rôles (6 ici) : résolution de session (1)
    # + `has_permission` de la garde (3, cf. test_authorization.py) +
    # `list_all` (2 : `Role`, `RolePermission`) + `count_holders_by_role` (1,
    # agrégée). Avant #625 : 1 + 3 + 1 + (2 requêtes par rôle listé) — un
    # sixième rôle en plus aurait fait grimper ce total, ici il ne bouge pas.
    assert len(requetes) == 7, requetes
