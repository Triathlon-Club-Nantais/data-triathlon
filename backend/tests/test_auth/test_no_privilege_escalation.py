"""Nul n'accorde un pouvoir qu'il ne porte pas (#115, FR-011).

**Sans cette règle, `roles:write` équivaut à `root`** : quiconque édite les rôles
se fabrique en trois clics celui qui peut tout. Elle est sans effet pour un
superutilisateur, qui porte déjà l'inventaire, et c'est précisément ce qui rend
la délégation possible.

Elle est **bornée à l'inventaire**, à l'octroi comme au retrait. La borne n'est
pas une précaution : c'est la condition de réversibilité (voir
`test_stale_permissions.py`).
"""
from app.core.permissions import P
from app.models.role import Role
from app.models.role_permission import RolePermission

PERIME = "seasons:archive"


def test_creer_un_role_portant_un_pouvoir_qu_on_n_a_pas_rend_403(
    client, ouvrir_session
):
    ouvrir_session(P.ROLES_WRITE)

    reponse = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "archivist",
            "name": "Archiviste",
            "permissions": [P.PARTICIPATIONS_DELETE.code],
        },
    )

    assert reponse.status_code == 403


def test_ajouter_par_patch_un_pouvoir_qu_on_n_a_pas_rend_403(client, ouvrir_session):
    ouvrir_session(P.ROLES_WRITE)
    role = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": []},
    ).json()

    reponse = client.patch(
        f"/api/v1/admin/roles/{role['id']}",
        json={"permissions": [P.PARTICIPATIONS_DELETE.code]},
    )

    assert reponse.status_code == 403


def test_retirer_par_patch_un_pouvoir_qu_on_n_a_pas_rend_403(
    client, ouvrir_session, db_session
):
    """Le **retrait** aussi : autrement, un éditeur pourrait désarmer un rôle
    dont il ne comprend pas le périmètre."""
    ouvrir_session(P.ROLES_WRITE)
    role = Role(slug="archivist", name="Archiviste")
    role.permissions.append(
        RolePermission(permission_code=P.PARTICIPATIONS_DELETE.code)
    )
    db_session.add(role)
    db_session.commit()

    reponse = client.patch(
        f"/api/v1/admin/roles/{role.id}", json={"permissions": []}
    )

    assert reponse.status_code == 403


def test_attribuer_un_role_portant_un_pouvoir_qu_on_n_a_pas_rend_403(
    client, ouvrir_session, db_session, organisation
):
    ouvrir_session(P.ROLES_ASSIGN)
    cible = ouvrir_session(pose_le_cookie=False)
    role = Role(slug="archivist", name="Archiviste")
    role.permissions.append(
        RolePermission(permission_code=P.PARTICIPATIONS_DELETE.code)
    )
    db_session.add(role)
    db_session.commit()

    reponse = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": role.id, "organisation_id": organisation.id},
    )

    assert reponse.status_code == 403


def test_accorder_un_pouvoir_qu_on_porte_aboutit(client, ouvrir_session):
    """La contrepartie, sans quoi la règle serait un simple blocage."""
    ouvrir_session(P.ROLES_WRITE, P.QUALITY_OVERRIDE)

    reponse = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "archivist",
            "name": "Archiviste",
            "permissions": [P.QUALITY_OVERRIDE.code],
        },
    )

    assert reponse.status_code == 201


def test_un_superutilisateur_n_est_jamais_bloque_sur_un_code_de_l_inventaire(
    client, ouvrir_session
):
    """C'est ce qui rend la délégation possible : il porte déjà tout."""
    ouvrir_session(superutilisateur=True)

    reponse = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "archivist",
            "name": "Archiviste",
            "permissions": [P.PARTICIPATIONS_DELETE.code, P.ROLES_ASSIGN.code],
        },
    )

    assert reponse.status_code == 201


def test_un_code_perime_echappe_aux_quatre_controles(
    client, ouvrir_session, db_session, organisation
):
    """La borne, éprouvée sur les quatre chemins d'un coup.

    Le comparer gèlerait le rôle définitivement : personne ne porte un code hors
    inventaire, pas même un superutilisateur.
    """
    ouvrir_session(P.ROLES_WRITE, P.ROLES_ASSIGN)
    cible = ouvrir_session(pose_le_cookie=False)

    # 1. créer un rôle qui le porte — le code est refusé pour une autre raison
    #    (hors catalogue = 422), et non par la non-amplification.
    creation = client.post(
        "/api/v1/admin/roles",
        json={"slug": "archivist", "name": "Archiviste", "permissions": [PERIME]},
    )
    assert creation.status_code == 422

    role = Role(slug="ancien", name="Ancien")
    role.permissions.append(RolePermission(permission_code=PERIME))
    db_session.add(role)
    db_session.commit()

    # 2. le retirer par PATCH — permis, c'est le seul moyen de purge.
    assert (
        client.patch(f"/api/v1/admin/roles/{role.id}", json={"permissions": []}).status_code
        == 200
    )

    role.permissions.append(RolePermission(permission_code=PERIME))
    db_session.commit()

    # 3. attribuer le rôle qui le porte — permis.
    assert (
        client.post(
            f"/api/v1/admin/users/{cible.id}/roles",
            json={"role_id": role.id, "organisation_id": organisation.id},
        ).status_code
        == 201
    )

    # 4. retirer l'attribution — permis.
    assert (
        client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role.id}").status_code
        == 204
    )


def test_poser_is_superuser_sans_le_porter_rend_403(client, ouvrir_session):
    """FR-010 — le seul attribut qui ne se compose pas."""
    ouvrir_session(P.ROLES_WRITE)

    reponse = client.post(
        "/api/v1/admin/roles",
        json={
            "slug": "archivist",
            "name": "Archiviste",
            "permissions": [],
            "is_superuser": True,
        },
    )

    assert reponse.status_code == 403


def test_modifier_is_superuser_sans_le_porter_rend_403(
    client, ouvrir_session, db_session
):
    ouvrir_session(P.ROLES_WRITE)
    role = Role(slug="archivist", name="Archiviste")
    db_session.add(role)
    db_session.commit()

    reponse = client.patch(
        f"/api/v1/admin/roles/{role.id}", json={"is_superuser": True}
    )

    assert reponse.status_code == 403


# --- Le rôle superutilisateur ne se distribue pas non plus (#239) ------------
#
# Les deux tests ci-dessus gardent le **champ**. Ils ne suffisaient pas : la
# non-amplification compare les codes du rôle, et le rôle `admin` semé n'en
# porte **aucun** — il atteint tout par `is_superuser` (migration
# `f6a7b8c9d0e1`). Un porteur de `roles:assign` accordait donc l'administration
# entière, à quiconque et à lui-même, en franchissant un contrôle qui n'avait
# rien à comparer.


def _role_superutilisateur(db_session, *porteurs, organisation):
    """Un rôle superutilisateur **sans aucun code**, tel que le sème la migration."""
    from app.repositories import role_repository, user_role_repository

    role = role_repository.create(
        db_session, slug="root", name="Administrateur", is_superuser=True
    )
    db_session.flush()
    for porteur in porteurs:
        user_role_repository.grant(
            db_session,
            user_id=porteur.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    db_session.commit()
    return role


def test_attribuer_un_role_superutilisateur_sans_l_etre_rend_403(
    client, ouvrir_session, db_session, organisation
):
    """FR-010 au moment de l'**attribution**, et non seulement de la composition."""
    ouvrir_session(P.ROLES_ASSIGN)
    cible = ouvrir_session(pose_le_cookie=False)
    role = _role_superutilisateur(db_session, organisation=organisation)

    reponse = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": role.id, "organisation_id": organisation.id},
    )

    assert reponse.status_code == 403


def test_retirer_un_role_superutilisateur_sans_l_etre_rend_403(
    client, ouvrir_session, db_session, organisation
):
    """Symétrique, et pour la même raison : destituer un administrateur est un
    geste d'administrateur. Deux porteurs, pour que le refus vienne de FR-010 et
    non de l'invariant du dernier administrateur, qui rendrait 409."""
    ouvrir_session(P.ROLES_ASSIGN)
    cible = ouvrir_session(pose_le_cookie=False)
    second = ouvrir_session(pose_le_cookie=False)
    role = _role_superutilisateur(db_session, cible, second, organisation=organisation)

    reponse = client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role.id}")

    assert reponse.status_code == 403


def test_un_superutilisateur_distribue_le_role_superutilisateur(
    client, ouvrir_session, db_session, organisation
):
    """La contrepartie, sans quoi plus personne ne pourrait déléguer."""
    ouvrir_session(superutilisateur=True)
    cible = ouvrir_session(pose_le_cookie=False)
    role = _role_superutilisateur(db_session, organisation=organisation)

    assert (
        client.post(
            f"/api/v1/admin/users/{cible.id}/roles",
            json={"role_id": role.id, "organisation_id": organisation.id},
        ).status_code
        == 201
    )
    assert (
        client.delete(f"/api/v1/admin/users/{cible.id}/roles/{role.id}").status_code
        == 204
    )
