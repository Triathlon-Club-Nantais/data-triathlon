"""Accès données des rôles et des attributions (#115).

Seule couche qui touche la `Session` (Principe II) : ce que ces tests éprouvent
est du SQL, pas de la règle métier — celle-ci vit dans `services/auth/`.
"""
from app.models.organisation import Organisation
from app.models.role_permission import RolePermission
from app.repositories import role_repository, user_repository, user_role_repository


def _organisation(db_session, slug="tcn") -> Organisation:
    organisation = Organisation(slug=slug, name=slug.upper())
    db_session.add(organisation)
    db_session.flush()
    return organisation


def _role(db_session, slug, *, organisation_id=None, superutilisateur=False, codes=()):
    role = role_repository.create(
        db_session,
        slug=slug,
        name=slug.capitalize(),
        organisation_id=organisation_id,
        is_superuser=superutilisateur,
    )
    for code in codes:
        role.permissions.append(RolePermission(permission_code=code))
    db_session.flush()
    return role


def test_un_role_se_resout_par_son_slug(db_session):
    _role(db_session, "validator")

    assert role_repository.find_in_scope(db_session, slug="validator").slug == "validator"
    assert role_repository.find_in_scope(db_session, slug="inexistant") is None


def test_le_role_propre_a_l_organisation_prime_sur_le_role_global(db_session):
    """Deux rôles peuvent partager un slug s'ils sont de portées différentes.

    Le plus spécifique gagne : sinon créer un `validator` propre au club serait
    sans effet, le global l'ayant toujours devancé.
    """
    organisation = _organisation(db_session)
    _role(db_session, "validator")
    propre = _role(db_session, "validator", organisation_id=organisation.id)

    trouve = role_repository.find_in_scope(
        db_session, slug="validator", organisation_id=organisation.id
    )

    assert trouve.id == propre.id


def test_le_role_global_sert_de_repli_quand_l_organisation_n_en_a_pas(db_session):
    organisation = _organisation(db_session)
    global_ = _role(db_session, "validator")

    trouve = role_repository.find_in_scope(
        db_session, slug="validator", organisation_id=organisation.id
    )

    assert trouve.id == global_.id


def test_lister_par_slug_rend_les_deux_portees(db_session):
    """Ce dont `grant-role` a besoin pour dire « ce rôle est propre à tel club »."""
    organisation = _organisation(db_session, "autre")
    _role(db_session, "archiviste", organisation_id=organisation.id)

    trouves = role_repository.list_by_slug(db_session, "archiviste")

    assert [role.organisation_id for role in trouves] == [organisation.id]


def test_compter_les_porteurs_d_un_role(db_session):
    """Le nombre que le 409 de suppression doit **nommer** (FR-007)."""
    organisation = _organisation(db_session)
    role = _role(db_session, "validator")
    for adresse in ("a@exemple.fr", "b@exemple.fr"):
        user = user_repository.create(db_session, email=adresse)
        db_session.flush()
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    db_session.flush()

    assert role_repository.count_holders(db_session, role.id) == 2


def test_attribuer_deux_fois_est_un_succes_sans_doublon(db_session):
    """FR-012 — l'idempotence tient à la **contrainte**, pas à une lecture.

    Deux exploitants attribuant le même rôle au même instant franchiraient tous
    deux une lecture préalable ; c'est l'`IntegrityError` rattrapée qui fait le
    travail, et c'est pour cela qu'elle est éprouvée ici.
    """
    organisation = _organisation(db_session)
    role = _role(db_session, "validator")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.flush()

    _, cree = user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )
    _, recree = user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=organisation.id
    )

    assert (cree, recree) == (True, False)
    assert role_repository.count_holders(db_session, role.id) == 1


def test_retirer_une_attribution_absente_est_un_succes(db_session):
    organisation = _organisation(db_session)
    role = _role(db_session, "validator")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.flush()

    assert (
        user_role_repository.revoke(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
        is False
    )


def test_compter_les_superutilisateurs_actifs_d_une_organisation(db_session):
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    validator = _role(db_session, "validator", codes=["quality:override"])
    for adresse, role in (
        ("a@exemple.fr", admin),
        ("b@exemple.fr", admin),
        ("c@exemple.fr", validator),
    ):
        user = user_repository.create(db_session, email=adresse)
        db_session.flush()
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=role.id,
            organisation_id=organisation.id,
        )
    db_session.flush()

    assert (
        user_role_repository.count_active_superusers(db_session, organisation.id) == 2
    )


def test_un_compte_desactive_ne_compte_pas_comme_administrateur_actif(db_session):
    """« Actifs » au sens de #114 : ses sessions sont déjà tombées.

    Sans cette condition, l'invariant du dernier administrateur laisserait une
    installation verrouillée derrière un compte qui ne peut plus se connecter.
    """
    organisation = _organisation(db_session)
    admin = _role(db_session, "admin", superutilisateur=True)
    for adresse, actif in (("a@exemple.fr", True), ("b@exemple.fr", False)):
        user = user_repository.create(db_session, email=adresse)
        user.is_active = actif
        db_session.flush()
        user_role_repository.grant(
            db_session,
            user_id=user.id,
            role_id=admin.id,
            organisation_id=organisation.id,
        )
    db_session.flush()

    assert (
        user_role_repository.count_active_superusers(db_session, organisation.id) == 1
    )


def test_les_superutilisateurs_se_comptent_par_organisation(db_session):
    tcn = _organisation(db_session, "tcn")
    autre = _organisation(db_session, "autre")
    admin = _role(db_session, "admin", superutilisateur=True)
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=admin.id, organisation_id=tcn.id
    )
    db_session.flush()

    assert user_role_repository.count_active_superusers(db_session, tcn.id) == 1
    assert user_role_repository.count_active_superusers(db_session, autre.id) == 0


def test_supprimer_un_role_est_possible_quand_personne_ne_le_porte(db_session):
    role = _role(db_session, "archiviste", codes=["quality:override"])

    role_repository.delete(db_session, role)
    db_session.flush()

    assert role_repository.list_all(db_session) == []
    assert db_session.query(RolePermission).count() == 0


def test_find_by_email_rend_une_liste(db_session):
    """`users.email` n'est **pas** unique, délibérément (#114, FR-003).

    Rendre un scalaire rouvrirait le choix au hasard que `grant-role` doit
    refuser : deux identités externes portant la même adresse donnent deux
    utilisateurs distincts.
    """
    for _ in range(2):
        user_repository.create(db_session, email="homonyme@exemple.fr")
    user_repository.create(db_session, email="seul@exemple.fr")
    db_session.flush()

    assert len(user_repository.find_by_email(db_session, "homonyme@exemple.fr")) == 2
    assert len(user_repository.find_by_email(db_session, "seul@exemple.fr")) == 1
    assert user_repository.find_by_email(db_session, "absent@exemple.fr") == []


def test_find_by_email_ignore_la_casse(db_session):
    user_repository.create(db_session, email="Prenom.Nom@Exemple.fr")
    db_session.flush()

    assert len(user_repository.find_by_email(db_session, "prenom.nom@exemple.fr")) == 1


def test_lister_les_utilisateurs(db_session):
    for adresse in ("b@exemple.fr", "a@exemple.fr"):
        user_repository.create(db_session, email=adresse)
    db_session.flush()

    assert [user.email for user in user_repository.list_all(db_session)] == [
        "a@exemple.fr",
        "b@exemple.fr",
    ]


def test_les_roles_d_un_utilisateur_se_lisent_par_organisation(db_session):
    tcn = _organisation(db_session, "tcn")
    autre = _organisation(db_session, "autre")
    role = _role(db_session, "validator")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.flush()
    user_role_repository.grant(
        db_session, user_id=user.id, role_id=role.id, organisation_id=tcn.id
    )
    db_session.flush()

    assert len(user_role_repository.list_for_user(db_session, user.id)) == 1
    assert (
        user_role_repository.list_for_user(
            db_session, user.id, organisation_id=autre.id
        )
        == []
    )


def test_compter_les_porteurs_d_un_role_sans_porteur(db_session):
    role = _role(db_session, "archiviste")

    assert role_repository.count_holders(db_session, role.id) == 0


def test_le_role_est_lisible_par_son_identifiant(db_session):
    role = _role(db_session, "validator")

    assert role_repository.get(db_session, role.id).slug == "validator"
    assert role_repository.get(db_session, 9999) is None


def test_l_organisation_par_defaut_est_l_unique_semee(db_session):
    """`grant-role --organisation` a une valeur par défaut, et une seule cible."""
    organisation = _organisation(db_session)

    assert role_repository.default_organisation(db_session).id == organisation.id


def test_l_organisation_par_defaut_est_absente_sur_une_base_vierge(db_session):
    assert role_repository.default_organisation(db_session) is None
