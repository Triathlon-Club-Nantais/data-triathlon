"""Les deux tables de #197 et leurs contraintes (AC1, AC5, FR-007, FR-008).

Le schéma éprouvé est celui que `Base.metadata.create_all` construit depuis les
modèles — c'est celui que voit toute la suite. Une contrainte déclarée seulement
dans la révision Alembic n'existerait dans aucun test : d'où `__table_args__` sur
les modèles, et `tests/test_migrations.py` pour l'autre bout.
"""
import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.group import Group
from app.models.organisation import Organisation
from app.models.user import User
from app.models.user_group import UserGroup
from app.repositories import user_repository


@pytest.fixture
def organisations(db_session) -> tuple[Organisation, Organisation]:
    first = Organisation(slug="tcn", name="Triathlon Club Nantais")
    second = Organisation(slug="autre", name="Autre club")
    db_session.add_all([first, second])
    db_session.flush()
    return first, second


def test_two_groups_with_the_same_slug_in_one_organisation_are_refused(
    db_session, organisations
):
    tcn, _ = organisations
    db_session.add(Group(organisation_id=tcn.id, slug="codir", name="Codir"))
    db_session.flush()

    db_session.add(Group(organisation_id=tcn.id, slug="codir", name="Doublon"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_the_same_slug_is_free_in_another_organisation(db_session, organisations):
    """L'unicité porte sur le couple, pas sur le slug seul : deux clubs ont chacun
    leur Codir."""
    tcn, other = organisations
    db_session.add(Group(organisation_id=tcn.id, slug="codir", name="Codir"))
    db_session.add(Group(organisation_id=other.id, slug="codir", name="Codir"))

    db_session.flush()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(Group)) == 2


def test_a_group_without_an_organisation_is_refused(db_session):
    """La quatrième différence avec `Role`, et elle est structurelle.

    `roles.organisation_id` est **nullable** — un rôle global est une définition
    réutilisable. Un groupe est une composition, celle d'un club précis :
    « Codir » sans club ne désigne rien. C'est ce `NOT NULL` qui dispense
    `groups` de l'index partiel double dialecte qui garde `roles.slug`, et
    `user_groups` de toute colonne d'organisation.
    """
    db_session.add(Group(slug="codir", name="Codir"))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_the_same_person_cannot_join_a_group_twice(
    db_session, organisations
):
    """FR-008 — l'idempotence est portée par la contrainte, jamais par une lecture."""
    tcn, _ = organisations
    group = Group(organisation_id=tcn.id, slug="codir", name="Codir")
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.add(group)
    db_session.flush()

    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.flush()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_deleting_a_user_takes_their_memberships_and_leaves_the_group(
    db_session, organisations
):
    """AC5 — cascade ORM depuis `User.groups`, patron exact de `User.roles`.

    Le groupe survit : supprimer quelqu'un ne dissout pas la commission dont il
    faisait partie.
    """
    tcn, _ = organisations
    group = Group(organisation_id=tcn.id, slug="codir", name="Codir")
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.add(group)
    db_session.flush()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.flush()

    db_session.delete(user)
    db_session.flush()

    assert db_session.scalar(sa.select(sa.func.count()).select_from(UserGroup)) == 0
    assert db_session.get(Group, group.id) is not None


def test_deleting_a_group_does_not_cascade_to_its_members():
    """L'autre moitié de la règle de suppression (FR-011).

    Le refus d'effacer un groupe peuplé est prononcé par le service ; s'il était
    doublé d'une cascade ORM, il ne tiendrait plus que par le chemin — un appel
    direct viderait la table sans le dire. `Role` ne cascade pas non plus vers
    ses porteurs, pour ce motif exact.
    """
    assert "delete" not in (Group.__mapper__.relationships["members"].cascade)


def test_a_membership_carries_no_organisation():
    """Le groupe la porte déjà.

    La répéter ici rendrait représentable un état incohérent
    (`user_groups.organisation_id ≠ groups.organisation_id`) qu'aucune contrainte
    portable ne fermerait. `user_roles` en porte une pour la raison inverse : un
    rôle **global** doit dire où il s'applique.
    """
    assert "organisation_id" not in UserGroup.__table__.columns


def test_a_group_carries_neither_privilege_nor_system_flag():
    """FR-017 et FR-005 — un groupe n'accorde rien, et aucun n'est semé."""
    columns = set(Group.__table__.columns.keys())

    assert columns == {
        "id",
        "organisation_id",
        "slug",
        "name",
        "description",
        "created_at",
    }
    assert "is_superuser" not in columns
    assert "is_system" not in columns


def test_memberships_are_readable_from_the_user(
    db_session, organisations
):
    """`User.groups` est ce que lit `GET /auth/me`, sur le patron de `User.roles`."""
    tcn, _ = organisations
    group = Group(organisation_id=tcn.id, slug="codir", name="Codir")
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.add(group)
    db_session.flush()
    db_session.add(UserGroup(user_id=user.id, group_id=group.id))
    db_session.flush()

    reloaded = db_session.get(User, user.id)

    assert [membership.group.slug for membership in reloaded.groups] == ["codir"]
