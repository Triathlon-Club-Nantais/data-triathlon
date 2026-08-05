"""Les quatre tables de #115 et leurs contraintes (FR-005, FR-012, FR-013).

Le schéma est celui que `Base.metadata.create_all` construit — c'est celui que
voit toute la suite. Un index déclaré seulement dans la révision Alembic
n'existerait dans aucun test : d'où `__table_args__` sur les modèles.
"""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.organisation import Organisation
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User
from app.models.user_role import UserRole
from app.repositories import user_repository


@pytest.fixture
def organisations(db_session) -> tuple[Organisation, Organisation]:
    premiere = Organisation(slug="tcn", name="Triathlon Club Nantais")
    seconde = Organisation(slug="autre", name="Autre club")
    db_session.add_all([premiere, seconde])
    db_session.flush()
    return premiere, seconde


def test_deux_roles_de_meme_slug_dans_la_meme_organisation_sont_refuses(
    db_session, organisations
):
    tcn, _ = organisations
    db_session.add(Role(organisation_id=tcn.id, slug="archiviste", name="Archiviste"))
    db_session.flush()

    db_session.add(Role(organisation_id=tcn.id, slug="archiviste", name="Doublon"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deux_roles_globaux_de_meme_slug_sont_refuses(db_session):
    """Le piège que `UniqueConstraint(organisation_id, slug)` **ne** ferme pas.

    SQLite comme PostgreSQL tiennent deux `NULL` pour distincts : sans l'index
    partiel `WHERE organisation_id IS NULL`, deux rôles globaux `admin`
    coexisteraient, et `grant-role --role admin` n'aurait plus de cible.
    """
    db_session.add(Role(organisation_id=None, slug="admin", name="Administrateur"))
    db_session.flush()

    db_session.add(Role(organisation_id=None, slug="admin", name="Doublon"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_le_meme_slug_dans_deux_organisations_est_accepte(db_session, organisations):
    """La contrepartie : l'index partiel ne doit **pas** être un index complet.

    N'en déclarer qu'un des deux dialectes produit un index complet sur l'autre
    moteur, ce qui interdirait ce cas silencieusement — en production seulement.
    """
    tcn, autre = organisations
    db_session.add_all(
        [
            Role(organisation_id=tcn.id, slug="archiviste", name="Archiviste"),
            Role(organisation_id=autre.id, slug="archiviste", name="Archiviste"),
        ]
    )
    db_session.flush()

    assert db_session.query(Role).filter_by(slug="archiviste").count() == 2


def test_un_role_global_et_un_role_d_organisation_peuvent_partager_un_slug(
    db_session, organisations
):
    tcn, _ = organisations
    db_session.add_all(
        [
            Role(organisation_id=None, slug="validator", name="Validateur"),
            Role(organisation_id=tcn.id, slug="validator", name="Validateur du TCN"),
        ]
    )
    db_session.flush()

    assert db_session.query(Role).filter_by(slug="validator").count() == 2


def test_un_role_ne_porte_pas_deux_fois_le_meme_pouvoir(db_session):
    role = Role(slug="moderator", name="Modérateur")
    db_session.add(role)
    db_session.flush()

    db_session.add(
        RolePermission(role_id=role.id, permission_code="pending_providers:read")
    )
    db_session.flush()
    db_session.add(
        RolePermission(role_id=role.id, permission_code="pending_providers:read")
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_supprimer_un_role_emporte_ses_pouvoirs(db_session):
    role = Role(slug="archiviste", name="Archiviste")
    role.permissions.append(RolePermission(permission_code="quality:override"))
    db_session.add(role)
    db_session.flush()

    db_session.delete(role)
    db_session.flush()

    assert db_session.query(RolePermission).count() == 0


def test_une_attribution_est_unique_par_utilisateur_role_et_organisation(
    db_session, organisations
):
    """C'est **elle** qui rend l'attribution idempotente sous concurrence (FR-012).

    Pas une lecture préalable : deux exploitants attribuant le même rôle au même
    instant passeraient tous deux la lecture.
    """
    tcn, _ = organisations
    role = Role(slug="validator", name="Validateur")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.add(role)
    db_session.flush()

    db_session.add(UserRole(user_id=user.id, role_id=role.id, organisation_id=tcn.id))
    db_session.flush()
    db_session.add(UserRole(user_id=user.id, role_id=role.id, organisation_id=tcn.id))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_le_meme_role_est_attribuable_dans_deux_organisations(db_session, organisations):
    tcn, autre = organisations
    role = Role(slug="validator", name="Validateur")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.add(role)
    db_session.flush()

    db_session.add_all(
        [
            UserRole(user_id=user.id, role_id=role.id, organisation_id=tcn.id),
            UserRole(user_id=user.id, role_id=role.id, organisation_id=autre.id),
        ]
    )
    db_session.flush()

    assert db_session.query(UserRole).count() == 2


def test_supprimer_un_utilisateur_emporte_ses_attributions(db_session, organisations):
    """FR-013, par la **cascade ORM** et non par un `ondelete`.

    `core/database.py` n'émet aucun `PRAGMA foreign_keys=ON` : une contrainte de
    base serait inerte en SQLite et active en PostgreSQL. La cascade ORM couvre
    les deux moteurs, sur le patron exact de `User.identities` (#114).
    """
    tcn, _ = organisations
    role = Role(slug="validator", name="Validateur")
    user = user_repository.create(db_session, email="a@exemple.fr")
    db_session.add(role)
    db_session.flush()
    user.roles.append(UserRole(role_id=role.id, organisation_id=tcn.id))
    db_session.flush()

    db_session.delete(user)
    db_session.flush()

    assert db_session.query(UserRole).count() == 0
    assert db_session.query(Role).count() == 1, "le rôle, lui, survit"


def test_users_ne_porte_toujours_aucune_colonne_de_role(db_session):
    """#114 le promettait, #115 le tient — vérifié sur le **schéma appliqué**.

    On est administrateur *d'un club* : le rôle vit dans `user_roles`, jamais en
    scalaire ici. Un `role` posé sur `users` serait à défaire par une migration
    destructive au premier utilisateur ayant deux rôles dans deux clubs.
    """
    colonnes = {c["name"] for c in sa.inspect(db_session.bind).get_columns("users")}

    assert not {nom for nom in colonnes if "role" in nom}
    assert User.__tablename__ == "users"
