"""L'accès données des groupes (#197) — idempotence, comptes et ordre d'affichage.

Le point non trivial est `add_member` : l'insertion est tentée **d'abord**, sous
point de reprise, et c'est délibéré. Une lecture préalable serait franchie par
deux exploitants simultanés, là où `UNIQUE(user_id, group_id)` ne l'est jamais.
Reprise exacte du raisonnement de `user_role_repository.grant`.
"""
import pytest

from app.models.organisation import Organisation
from app.repositories import group_repository, user_repository


@pytest.fixture
def organisation(db_session) -> Organisation:
    ligne = Organisation(slug="tcn", name="Triathlon Club Nantais")
    db_session.add(ligne)
    db_session.flush()
    return ligne


@pytest.fixture
def group(db_session, organisation):
    return group_repository.create(
        db_session, organisation_id=organisation.id, slug="codir", name="Codir"
    )


def test_adding_the_same_member_twice_is_idempotent(db_session, group):
    """FR-008 — le second appel rend l'existante et dit qu'il n'a rien créé."""
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.flush()

    first, created = group_repository.add_member(
        db_session, group_id=group.id, user_id=user.id
    )
    second, recreated = group_repository.add_member(
        db_session, group_id=group.id, user_id=user.id
    )

    assert created is True
    assert recreated is False
    assert second.id == first.id
    assert group_repository.count_members(db_session, group.id) == 1


def test_idempotency_does_not_lose_the_pending_transaction(db_session, group):
    """Le `SAVEPOINT` est ce qui permet de rattraper la violation sans tout perdre.

    Sans lui, l'`IntegrityError` invaliderait la transaction et l'écriture qui
    précède — ici la création d'un second groupe — disparaîtrait avec elle.
    """
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.flush()
    group_repository.add_member(db_session, group_id=group.id, user_id=user.id)
    other = group_repository.create(
        db_session, organisation_id=group.organisation_id, slug="arbitres", name="Arbitres"
    )

    group_repository.add_member(db_session, group_id=group.id, user_id=user.id)

    assert db_session.get(type(other), other.id) is not None


def test_removing_an_absent_member_does_not_raise(db_session, group):
    """FR-009 — idempotent dans l'autre sens, patron de `user_role_repository.revoke`."""
    user = user_repository.create(db_session, email="membre@exemple.fr")
    db_session.flush()

    assert group_repository.remove_member(db_session, group_id=group.id, user_id=user.id) is False

    group_repository.add_member(db_session, group_id=group.id, user_id=user.id)

    assert group_repository.remove_member(db_session, group_id=group.id, user_id=user.id) is True
    assert group_repository.count_members(db_session, group.id) == 0


def test_members_come_out_in_display_order(db_session, group):
    """Par `display_name`, puis par adresse — un ordre stable, pas celui d'insertion.

    Sans tri explicite, la liste sortirait dans l'ordre des identifiants, donc
    dans l'ordre où les gens se sont connectés pour la première fois.
    """
    zoe = user_repository.create(db_session, email="a@exemple.fr", display_name="Zoé Martin")
    alix = user_repository.create(db_session, email="z@exemple.fr", display_name="Alix Roux")
    db_session.flush()
    group_repository.add_member(db_session, group_id=group.id, user_id=zoe.id)
    group_repository.add_member(db_session, group_id=group.id, user_id=alix.id)

    members = group_repository.list_members(db_session, group.id)

    assert [membership.user.display_name for membership in members] == [
        "Alix Roux",
        "Zoé Martin",
    ]


def test_groups_come_out_sorted_by_slug(db_session, organisation):
    group_repository.create(
        db_session, organisation_id=organisation.id, slug="codir", name="Codir"
    )
    group_repository.create(
        db_session, organisation_id=organisation.id, slug="arbitres", name="Arbitres"
    )

    assert [group.slug for group in group_repository.list_all(db_session)] == [
        "arbitres",
        "codir",
    ]


def test_find_in_scope_does_not_cross_organisations(db_session, organisation):
    """Le slug est unique **dans un club**, pas dans l'installation."""
    other = Organisation(slug="autre", name="Autre club")
    db_session.add(other)
    db_session.flush()
    group_repository.create(
        db_session, organisation_id=organisation.id, slug="codir", name="Codir"
    )

    assert (
        group_repository.find_in_scope(
            db_session, slug="codir", organisation_id=organisation.id
        )
        is not None
    )
    assert (
        group_repository.find_in_scope(db_session, slug="codir", organisation_id=other.id)
        is None
    )
