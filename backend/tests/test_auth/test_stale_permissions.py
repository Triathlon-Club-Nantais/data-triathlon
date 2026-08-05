"""Les pouvoirs périmés (#115, FR-042) — inertes, purgeables, **jamais bloquants**.

Une suppression de fonctionnalité ordinaire laisse des lignes `role_permissions`
dont le code n'est plus dans l'inventaire. Trois propriétés, et la troisième est
celle qui a failli manquer : elles n'accordent rien, elles ne cassent rien, et
elles ne **gèlent** pas le rôle qui les porte.
"""
from app.core.permissions import P
from app.models.role import Role
from app.models.role_permission import RolePermission

#: Un pouvoir qu'une livraison aurait retiré du catalogue.
PERIME = "seasons:archive"


def _role_perime(db_session, *, systeme=False) -> Role:
    role = Role(slug="ancien", name="Ancien rôle", is_system=systeme)
    role.permissions.append(RolePermission(permission_code=PERIME))
    role.permissions.append(RolePermission(permission_code=P.QUALITY_OVERRIDE.code))
    db_session.add(role)
    db_session.commit()
    return role


def test_un_code_perime_ressort_a_part_et_jamais_dans_les_pouvoirs(
    client, ouvrir_session, db_session
):
    """`stale_permissions` : hygiène, jamais correction."""
    ouvrir_session(P.ROLES_READ)
    role = _role_perime(db_session)

    lecture = client.get(f"/api/v1/admin/roles/{role.id}").json()

    assert lecture["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert lecture["stale_permissions"] == [PERIME]


def test_un_code_perime_n_accorde_rien_et_ne_fait_pas_lever(
    client, ouvrir_session, db_session, organisation
):
    from app.repositories import user_role_repository

    porteur = ouvrir_session()
    role = _role_perime(db_session)
    user_role_repository.grant(
        db_session,
        user_id=porteur.id,
        role_id=role.id,
        organisation_id=organisation.id,
    )
    db_session.commit()

    # Le code périmé n'ouvre rien ; celui du catalogue, qui vit dans le **même**
    # rôle, ouvre normalement — la ligne inerte ne contamine pas sa voisine.
    assert client.get("/api/v1/admin/roles").status_code == 403
    assert client.get("/api/v1/admin/permissions").status_code == 403


def test_un_patch_omettant_le_code_perime_aboutit_et_le_purge(
    client, ouvrir_session, db_session
):
    """**Le** moyen de purge : il n'existe aucune ressource dédiée.

    `permissions` remplace l'ensemble, donc omettre un code périmé le supprime.
    Cela n'est vrai qu'à une condition, et elle est structurante : la
    non-amplification ne compare que les codes de l'inventaire (FR-011).
    """
    ouvrir_session(P.ROLES_WRITE, P.QUALITY_OVERRIDE)
    role = _role_perime(db_session)

    reponse = client.patch(
        f"/api/v1/admin/roles/{role.id}",
        json={"permissions": [P.QUALITY_OVERRIDE.code]},
    )

    assert reponse.status_code == 200
    assert reponse.json()["stale_permissions"] == []
    assert db_session.query(RolePermission).filter_by(permission_code=PERIME).count() == 0


def test_la_purge_vaut_aussi_pour_un_superutilisateur(
    client, ouvrir_session, db_session
):
    """Le cas qui aurait gelé le rôle **pour toujours**.

    Les pouvoirs effectifs d'un superutilisateur *sont* l'inventaire : il ne
    porte pas plus un code périmé que les autres. Si la non-amplification les
    comparait, personne — pas même lui — ne pourrait les retirer, et le rôle,
    `is_system` ou attribué, serait indélébile par-dessus le marché.
    """
    ouvrir_session(superutilisateur=True)
    role = _role_perime(db_session, systeme=True)

    reponse = client.patch(
        f"/api/v1/admin/roles/{role.id}", json={"permissions": []}
    )

    assert reponse.status_code == 200
    assert reponse.json()["permissions"] == []
    assert reponse.json()["stale_permissions"] == []


def test_un_role_portant_un_code_perime_reste_attribuable(
    client, ouvrir_session, db_session, organisation
):
    """Sans cette borne, tout rôle ayant survécu à une suppression de
    fonctionnalité deviendrait **inattribuable**, personne ne portant son code."""
    ouvrir_session(P.ROLES_ASSIGN, P.QUALITY_OVERRIDE)
    cible = ouvrir_session(pose_le_cookie=False)
    role = _role_perime(db_session)

    reponse = client.post(
        f"/api/v1/admin/users/{cible.id}/roles",
        json={"role_id": role.id, "organisation_id": organisation.id},
    )

    assert reponse.status_code == 201


def test_un_role_portant_un_code_perime_reste_supprimable(
    client, ouvrir_session, db_session
):
    ouvrir_session(P.ROLES_WRITE, P.QUALITY_OVERRIDE)
    role = _role_perime(db_session)

    assert client.delete(f"/api/v1/admin/roles/{role.id}").status_code == 204
