"""La décision d'accès (#115, FR-009, FR-014, FR-016, FR-042).

Elle relit la base à chaque appel. C'est ce qui rend l'édition d'un rôle
effective **à la requête suivante** de tous ses porteurs, sans reconnexion — et
c'est ce qu'un cache, si petit soit-il, rendrait faux.
"""
from app.core.permissions import CODES, P
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import role_repository, user_repository, user_role_repository
from app.services.auth import authorization


def _organisation(db_session, slug="tcn") -> Organisation:
    organisation = Organisation(slug=slug, name=slug.upper())
    db_session.add(organisation)
    db_session.flush()
    return organisation


def _role(db_session, slug, *, codes=(), superutilisateur=False):
    role = role_repository.create(
        db_session, slug=slug, name=slug.capitalize(), is_superuser=superutilisateur
    )
    for code in codes:
        role.permissions.append(RolePermission(permission_code=code))
    db_session.flush()
    return role


def _porteur(db_session, organisation, *roles, email="a@exemple.fr", actif=True):
    user = user_repository.create(db_session, email=email)
    user.is_active = actif
    db_session.flush()
    for role in roles:
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    db_session.flush()
    return user


def test_un_connecte_sans_role_ne_porte_aucun_pouvoir(db_session):
    organisation = _organisation(db_session)
    user = _porteur(db_session, organisation)

    assert authorization.effective_permissions(db_session, user) == frozenset()
    assert authorization.has_permission(db_session, user, P.ROLES_READ) is False


def test_les_pouvoirs_effectifs_sont_l_union_des_roles_portes(db_session):
    """Edge case « un utilisateur porte plusieurs rôles ».

    Union, jamais intersection ni « le premier gagne » : deux rôles se cumulent,
    c'est tout l'intérêt de les composer.
    """
    organisation = _organisation(db_session)
    lecteur = _role(db_session, "lecteur", codes=[P.ROLES_READ.code])
    qualite = _role(db_session, "qualite", codes=[P.QUALITY_OVERRIDE.code])
    user = _porteur(db_session, organisation, lecteur, qualite)

    assert authorization.effective_permissions(db_session, user) == {
        P.ROLES_READ.code,
        P.QUALITY_OVERRIDE.code,
    }


def test_un_superutilisateur_franchit_un_code_qu_aucun_de_ses_roles_ne_porte(db_session):
    """FR-009 — et son `role_permissions` est **vide**, c'est le point.

    Le semis ne lui colle aucun code : lui donner les neuf du jour le figerait au
    jour d'aujourd'hui, ce que ce booléen évite précisément.
    """
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    user = _porteur(db_session, organisation, admin)

    assert admin.permissions == []
    for pouvoir in (P.ROLES_WRITE, P.QUALITY_OVERRIDE, P.PARTICIPATIONS_DELETE):
        assert authorization.has_permission(db_session, user, pouvoir) is True


def test_un_superutilisateur_franchit_un_pouvoir_invente_apres_coup(db_session):
    """SC-006 — la promesse qui rend une livraison indolore (FR-014).

    Une fonctionnalité livrée mardi doit être administrable mardi : ni migration
    de données, ni recochage, ni même que l'exploitant sache qu'elle a eu lieu.
    """
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    user = _porteur(db_session, organisation, admin)

    assert authorization.has_permission(db_session, user, "seasons:archive") is True


def test_les_pouvoirs_effectifs_d_un_superutilisateur_sont_le_catalogue(db_session):
    """C'est **cette** égalité qui rend un code périmé retirable par tout le monde.

    Un superutilisateur ne porte pas plus un code hors inventaire que les
    autres : si la non-amplification les comparait, personne ne pourrait les
    purger, et le rôle qui en traîne un serait gelé pour toujours (FR-011).
    """
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    user = _porteur(db_session, organisation, admin)

    assert authorization.effective_permissions(db_session, user) == CODES


def test_un_code_absent_du_catalogue_n_accorde_rien_et_ne_fait_pas_lever(db_session):
    """FR-042 — un pouvoir retiré par une livraison laisse des lignes **inertes**.

    Elles ne doivent ni accorder quoi que ce soit, ni casser la décision : la
    garde ne demande jamais « quels codes ce rôle porte-t-il ? » mais
    « porte-t-il *ce* code ? ».
    """
    organisation = _organisation(db_session)
    perime = _role(
        db_session, "perime", codes=["seasons:archive", P.ROLES_READ.code]
    )
    user = _porteur(db_session, organisation, perime)

    pouvoirs = authorization.effective_permissions(db_session, user)

    assert pouvoirs == {P.ROLES_READ.code}
    assert authorization.has_permission(db_session, user, "seasons:archive") is False


def test_un_compte_desactive_ne_porte_plus_aucun_pouvoir(db_session):
    """Ceinture et bretelles : la session est déjà tombée (#114), le 401 précède.

    Mais la décision ne doit pas *supposer* que la session l'a filtré — elle est
    appelée par la CLI aussi, où il n'y a pas de session du tout.
    """
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    user = _porteur(db_session, organisation, admin, actif=False)

    assert authorization.has_permission(db_session, user, P.ROLES_READ) is False
    assert authorization.effective_permissions(db_session, user) == frozenset()


def test_les_pouvoirs_se_lisent_par_organisation(db_session):
    tcn = _organisation(db_session, "tcn")
    autre = _organisation(db_session, "autre")
    qualite = _role(db_session, "qualite", codes=[P.QUALITY_OVERRIDE.code])
    user = _porteur(db_session, tcn, qualite)

    assert authorization.effective_permissions(
        db_session, user, organisation_id=tcn.id
    ) == {P.QUALITY_OVERRIDE.code}
    assert (
        authorization.effective_permissions(db_session, user, organisation_id=autre.id)
        == frozenset()
    )


def test_la_decision_relit_la_base_et_ne_met_rien_en_cache(db_session):
    """FR-016 — le changement s'applique à la **requête suivante** du porteur.

    Un cache, si petit soit-il, ferait de l'édition à chaud une promesse fausse :
    « c'est effectif tout de suite » deviendrait « au bout d'un moment ».
    """
    organisation = _organisation(db_session)
    role = _role(db_session, "qualite", codes=[P.QUALITY_OVERRIDE.code])
    user = _porteur(db_session, organisation, role)
    assert authorization.has_permission(db_session, user, P.QUALITY_OVERRIDE) is True

    role.permissions.clear()
    db_session.flush()

    assert authorization.has_permission(db_session, user, P.QUALITY_OVERRIDE) is False


def test_ajouter_un_pouvoir_a_un_role_est_effectif_pour_tous_ses_porteurs(db_session):
    """SC-005 — et **sans reconnexion** : le rôle est lu, pas recopié à l'ouverture."""
    organisation = _organisation(db_session)
    role = _role(db_session, "qualite")
    premier = _porteur(db_session, organisation, role, email="a@exemple.fr")
    second = _porteur(db_session, organisation, role, email="b@exemple.fr")

    role.permissions.append(RolePermission(permission_code=P.QUALITY_OVERRIDE.code))
    db_session.flush()

    for user in (premier, second):
        assert authorization.has_permission(db_session, user, P.QUALITY_OVERRIDE) is True


def test_retirer_un_pouvoir_ne_deconnecte_personne(db_session):
    """Edge Case — **retirer un pouvoir n'est pas déconnecter quelqu'un**.

    La session reste valide : son invariant (#114) porte sur l'existence, la
    péremption et l'activité du compte, jamais sur les rôles. Une session
    invalidée à chaque édition de rôle ferait de la composition à chaud une
    opération hostile, et rien ne le justifie — la personne reste la personne.
    """
    from app.services.auth import session as session_service

    organisation = _organisation(db_session)
    role = _role(db_session, "qualite", codes=[P.QUALITY_OVERRIDE.code])
    user = _porteur(db_session, organisation, role)
    jeton = session_service.open_for(db_session, user)
    db_session.flush()

    role.permissions.clear()
    db_session.flush()

    assert authorization.has_permission(db_session, user, P.QUALITY_OVERRIDE) is False
    assert session_service.resolve(db_session, jeton) is not None


def test_compter_les_superutilisateurs_actifs(db_session):
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    _porteur(db_session, organisation, admin)

    assert authorization.count_active_superusers(db_session, organisation.id) == 1


def _requetes(db_session, appel):
    """Compte les requêtes SQL émises par `appel()` (#625).

    Patron de `test_stats_service.test_course_summary_ne_charge_que_les_colonnes_utiles`.
    """
    from sqlalchemy import event

    requetes = []

    def _mouchard(conn, cursor, statement, *reste):
        requetes.append(statement)

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", _mouchard)
    try:
        appel()
    finally:
        event.remove(engine, "before_cursor_execute", _mouchard)
    return requetes


#: `UserRole` (`list_for_user`), puis `Role` et `RolePermission` — les deux
#: derniers en `selectinload`, donc chacun **une seule fois par lot**, jamais
#: une fois par rôle porté (#625).
REQUETES_UNE_RESOLUTION = 3


def test_has_permission_tient_en_un_nombre_de_requetes_fixe_quel_que_soit_le_nombre_de_roles(
    db_session,
):
    """#625 — `_is_superuser` puis `effective_permissions` relisaient chacun
    `list_for_user`, jusqu'à trois fois cette même résolution pour une
    décision qui n'en réclame qu'une, sans même compter le lazy-load de
    `.role`/`.role.permissions` par rôle porté avant l'ajout du `selectinload`.
    """
    organisation = _organisation(db_session)
    roles = [
        _role(db_session, f"role-{i}", codes=[f"code:{i}"]) for i in range(3)
    ]
    user = _porteur(db_session, organisation, *roles)
    db_session.commit()
    db_session.expire_all()
    # Un utilisateur relu à neuf, comme le ferait `current_user` sur une
    # requête HTTP — la fixture le crée dans la même session, garder l'objet
    # tel quel ferait compter la relecture de ses propres colonnes scalaires.
    user = user_repository.get(db_session, user.id)

    requetes = _requetes(
        db_session,
        lambda: authorization.has_permission(db_session, user, "code:1"),
    )

    assert len(requetes) == REQUETES_UNE_RESOLUTION, requetes


def test_effective_permissions_tient_en_un_nombre_de_requetes_fixe_quel_que_soit_le_nombre_de_roles(
    db_session,
):
    organisation = _organisation(db_session)
    roles = [
        _role(db_session, f"role-{i}", codes=[f"code:{i}"]) for i in range(3)
    ]
    user = _porteur(db_session, organisation, *roles)
    db_session.commit()
    db_session.expire_all()
    user = user_repository.get(db_session, user.id)

    requetes = _requetes(
        db_session, lambda: authorization.effective_permissions(db_session, user)
    )

    assert len(requetes) == REQUETES_UNE_RESOLUTION, requetes


def test_effective_permissions_n_interroge_pas_la_base_quand_les_attributions_sont_fournies(
    db_session,
):
    """`attributions=` (#625) — l'appelant qui les tient déjà (`GET /auth/me`,
    `user.roles` déjà chargé) ne doit provoquer aucun aller-retour DB de plus.
    """
    organisation = _organisation(db_session)
    role = _role(db_session, "qualite", codes=[P.QUALITY_OVERRIDE.code])
    user = _porteur(db_session, organisation, role)
    db_session.commit()
    db_session.expire_all()
    user = user_repository.get(db_session, user.id)
    attributions = user_role_repository.list_for_user(db_session, user.id)

    requetes = _requetes(
        db_session,
        lambda: authorization.effective_permissions(
            db_session, user, attributions=attributions
        ),
    )

    assert requetes == []
