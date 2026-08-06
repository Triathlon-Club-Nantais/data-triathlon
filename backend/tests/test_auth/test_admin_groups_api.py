"""Les sept ressources de `/api/v1/admin/groups` (#197).

Trois volets : l'écriture (US1), l'appartenance (US1) et la lecture (US2), plus
les gardes de chacun. Le filet de #115
(`test_public_routes_still_open.py`) prouve déjà qu'aucune de ces routes n'est
ouverte à l'anonyme — **sans avoir été modifié**, par la seule règle du préfixe
`/api/v1/admin/`. Ce fichier-ci éprouve ce que le filet ne peut pas dire : quel
pouvoir précis garde quoi, et ce que rendent les cas d'erreur.
"""
import logging

import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.core.permissions import P
from app.services.auth import session as session_service

BASE = "/api/v1/admin/groups"


@pytest.fixture
def group(client, ouvrir_session):
    """Un groupe « codir » créé par l'API, cookie laissé sur une session pleine."""
    ouvrir_session(superutilisateur=True)
    response = client.post(BASE, json={"slug": "codir", "name": "Codir"})
    assert response.status_code == 201
    return response.json()


# --- US1, volet écriture -----------------------------------------------------


def test_a_group_is_born_empty(client, ouvrir_session):
    """FR-004 — un groupe existe **avant** d'avoir des membres, et c'est ce qui le
    distingue d'un rôle : un rôle sans pouvoir n'a aucun sens."""
    ouvrir_session(P.GROUPS_WRITE)

    response = client.post(BASE, json={"slug": "arbitres", "name": "Arbitres"})

    assert response.status_code == 201
    body = response.json()
    assert body["member_count"] == 0
    assert body["members"] == []
    assert body["slug"] == "arbitres"
    assert body["organisation_id"] is not None


def test_a_slug_collision_under_concurrency_returns_409_not_500(
    client, ouvrir_session, monkeypatch
):
    """Le chemin que la lecture préalable **ne** couvre pas.

    Deux exploitants simultanés franchissent tous deux le `SELECT` ; seule
    `uq_group_org_slug` tranche. Sans point de reprise autour de l'écriture,
    l'`IntegrityError` remonte nue — aucun handler ne l'attrape, et le contrat
    promet pourtant un 409. La lecture est ici neutralisée pour simuler la
    course, ce qu'aucun test concurrent ne saurait rendre déterministe.
    """
    from app.repositories import group_repository

    ouvrir_session(P.GROUPS_WRITE)
    client.post(BASE, json={"slug": "codir", "name": "Codir"})
    monkeypatch.setattr(group_repository, "find_in_scope", lambda *a, **k: None)

    response = client.post(BASE, json={"slug": "codir", "name": "Doublon"})

    assert response.status_code == 409


def test_an_unknown_organisation_is_refused(client, ouvrir_session):
    """Sans `PRAGMA foreign_keys=ON`, SQLite accepterait la ligne et PostgreSQL
    la refuserait en 500 : le contrôle est fait en Python, pas laissé au moteur."""
    ouvrir_session(P.GROUPS_WRITE)

    response = client.post(
        BASE, json={"slug": "codir", "name": "Codir", "organisation_id": 9999}
    )

    assert response.status_code == 422


def test_two_groups_with_the_same_slug_in_one_club_are_refused(
    client, ouvrir_session
):
    ouvrir_session(P.GROUPS_WRITE)
    client.post(BASE, json={"slug": "codir", "name": "Codir"})

    response = client.post(BASE, json={"slug": "codir", "name": "Doublon"})

    assert response.status_code == 409


def test_a_malformed_slug_is_refused(client, ouvrir_session):
    ouvrir_session(P.GROUPS_WRITE)

    assert client.post(BASE, json={"slug": "Codir!", "name": "Codir"}).status_code == 422


def test_renaming_loses_no_membership(client, ouvrir_session, group):
    """FR-006 — le libellé bouge, l'identité et la composition ne bougent pas."""
    member = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    response = client.patch(
        f"{BASE}/{group['id']}", json={"name": "Comité de direction"}
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Comité de direction"
    assert response.json()["slug"] == "codir"
    assert response.json()["member_count"] == 1


def test_the_slug_cannot_be_renamed(client, ouvrir_session, group):
    """`extra="forbid"` — un 422, jamais un champ ignoré en silence."""
    response = client.patch(f"{BASE}/{group['id']}", json={"slug": "autre"})

    assert response.status_code == 422


def test_deleting_an_empty_group_succeeds(client, group):
    assert client.delete(f"{BASE}/{group['id']}").status_code == 204
    assert client.get(f"{BASE}/{group['id']}").status_code == 404


def test_deleting_a_populated_group_is_refused_and_names_the_count(
    client, ouvrir_session, group
):
    """FR-011 — le nombre est **dans le message** : « conflit » ne se corrige pas.

    Aucun droit n'est pourtant perdu : ce qu'on protège est la composition, qu'
    aucune migration ne reconstitue.
    """
    first = ouvrir_session(pose_le_cookie=False)
    second = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    for member in (first, second):
        client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    response = client.delete(f"{BASE}/{group['id']}")

    assert response.status_code == 409
    assert "2 membres" in response.json()["detail"]


def test_the_deletion_refusal_agrees_in_the_singular(client, ouvrir_session, group):
    member = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    detail = client.delete(f"{BASE}/{group['id']}").json()["detail"]

    assert "1 membre." in detail
    assert "Retirez-le" in detail


def test_emptying_a_group_then_deleting_it_succeeds(client, ouvrir_session, group):
    """FR-019 — il n'existe aucun invariant du dernier membre. Vider est libre."""
    member = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    assert client.delete(f"{BASE}/{group['id']}/members/{member.id}").status_code == 204
    assert client.delete(f"{BASE}/{group['id']}").status_code == 204


def test_creation_and_deletion_are_logged(
    client, ouvrir_session, caplog
):
    """FR-023 — l'audit de cette feature n'a pas de table : ces lignes **sont** la trace.

    En anglais (couche technique invisible), avec l'auteur et la cible, et sans
    aucun secret.
    """
    actor = ouvrir_session(superutilisateur=True)

    with caplog.at_level(logging.INFO, logger="app.services.auth.groups"):
        created = client.post(BASE, json={"slug": "codir", "name": "Codir"}).json()
        client.delete(f"{BASE}/{created['id']}")

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Group created" in message and f"actor={actor.id}" in message and "codir" in message
        for message in messages
    )
    assert any(
        "Group deleted" in message and f"actor={actor.id}" in message
        for message in messages
    )


# --- US1, volet appartenance -------------------------------------------------


def test_adding_a_member_twice_is_idempotent(client, ouvrir_session, group):
    """FR-008 — réajouter est un **succès**, sans doublon ni erreur exposée."""
    member = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    path = f"{BASE}/{group['id']}/members"

    premiere = client.post(path, json={"user_id": member.id})
    seconde = client.post(path, json={"user_id": member.id})

    assert premiere.status_code == 201
    assert seconde.status_code == 201
    assert seconde.json()["member_count"] == 1


def test_removing_someone_who_was_not_a_member_succeeds(
    client, ouvrir_session, group
):
    outsider = ouvrir_session(pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)

    response = client.delete(f"{BASE}/{group['id']}/members/{outsider.id}")

    assert response.status_code == 204


def test_removing_a_member_removes_nothing_else(client, ouvrir_session, group):
    """FR-009 — ni session, ni rôle, ni autre appartenance. **Les trois.**

    L'énoncé porte sur trois choses ; n'en asserter qu'une laisserait le
    docstring plus large que le test, ce qui est la façon la plus discrète de
    croire une propriété non vérifiée.
    """
    ouvrir_session(superutilisateur=True)
    other = client.post(BASE, json={"slug": "arbitres", "name": "Arbitres"}).json()
    member = ouvrir_session(P.GROUPS_READ, pose_le_cookie=False)
    ouvrir_session(superutilisateur=True)
    client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})
    client.post(f"{BASE}/{other['id']}/members", json={"user_id": member.id})

    client.delete(f"{BASE}/{group['id']}/members/{member.id}")

    # 1. l'autre appartenance
    assert client.get(f"{BASE}/{other['id']}").json()["member_count"] == 1
    # 2. la session du membre, et 3. le rôle qu'elle porte
    client.cookies.clear()
    client.cookies.set(
        session_cookie_name(get_settings()),
        session_service.open_for(_current_session(), member),
    )
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, "la session du membre retiré reste valide"
    assert me.json()["permissions"] == [str(P.GROUPS_READ)]
    assert [group["slug"] for group in me.json()["groups"]] == ["arbitres"]


def _current_session():
    """La `Session` que le `TestClient` sert, par la surcharge de `get_db`."""
    from app.core.database import get_db
    from app.main import app

    return next(app.dependency_overrides[get_db]())


def test_a_deactivated_account_is_a_legitimate_member(client, ouvrir_session, group, db_session):
    """Rien de ce que porte un groupe ne dépend de l'activité du compte.

    L'inverse — refuser l'appartenance d'un compte désactivé — traiterait le
    groupe comme un porteur de droits, ce qu'il n'est pas.
    """
    member = ouvrir_session(pose_le_cookie=False)
    member.is_active = False
    db_session.flush()
    ouvrir_session(superutilisateur=True)

    response = client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    assert response.status_code == 201
    assert response.json()["members"][0]["is_active"] is False


def test_adding_an_unknown_user_returns_404(client, ouvrir_session, group):
    assert (
        client.post(f"{BASE}/{group['id']}/members", json={"user_id": 9999}).status_code
        == 404
    )


def test_adding_and_removing_a_member_are_logged(client, ouvrir_session, group, caplog):
    """FR-023, seconde moitié : l'auteur, la cible et le **sens** de l'opération."""
    member = ouvrir_session(pose_le_cookie=False)
    actor = ouvrir_session(superutilisateur=True)

    with caplog.at_level(logging.INFO, logger="app.services.auth.groups"):
        client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})
        client.delete(f"{BASE}/{group['id']}/members/{member.id}")

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "Member added" in message
        and f"actor={actor.id}" in message
        and f"target_user={member.id}" in message
        for message in messages
    )
    assert any(
        "Member removed" in message and f"target_user={member.id}" in message
        for message in messages
    )


# --- US1, volet gardes -------------------------------------------------------

#: Les cinq ressources d'écriture, avec le pouvoir que chacune exige.
WRITES = [
    ("POST", BASE, {"slug": "x", "name": "X"}),
    ("PATCH", f"{BASE}/1", {"name": "X"}),
    ("DELETE", f"{BASE}/1", None),
    ("POST", f"{BASE}/1/members", {"user_id": 1}),
    ("DELETE", f"{BASE}/1/members/1", None),
]


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_a_write_resource_refuses_the_anonymous(client, method, path, body):
    """401, et **jamais** 403 : on ne dit pas « droits insuffisants » à qui n'est
    pas connecté — les deux réponses appellent deux gestes différents."""
    response = client.request(method, path, json=body)

    assert response.status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_a_write_resource_refuses_a_session_without_privilege(
    client, ouvrir_session, method, path, body
):
    ouvrir_session()

    response = client.request(method, path, json=body)

    assert response.status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), WRITES)
def test_groups_read_alone_passes_no_write(
    client, ouvrir_session, method, path, body
):
    """Les trois pouvoirs sont réellement distincts : consulter n'est pas composer."""
    ouvrir_session(P.GROUPS_READ)

    response = client.request(method, path, json=body)

    assert response.status_code == 403


def test_groups_write_does_not_pass_assignment(client, ouvrir_session, group):
    """Composer un groupe et en désigner les membres sont deux gestes, deux pouvoirs.

    C'est la séparation que #197 emprunte à #115 : `roles:write` ne vaut pas
    `roles:assign`.
    """
    ouvrir_session(P.GROUPS_WRITE)

    response = client.post(f"{BASE}/{group['id']}/members", json={"user_id": 1})

    assert response.status_code == 403


def test_groups_assign_does_not_pass_composition(client, ouvrir_session):
    ouvrir_session(P.GROUPS_ASSIGN)

    assert client.post(BASE, json={"slug": "x", "name": "X"}).status_code == 403


# --- US2, volet lecture ------------------------------------------------------


def test_the_list_comes_out_sorted_by_slug_with_the_count(client, ouvrir_session):
    ouvrir_session(superutilisateur=True)
    client.post(BASE, json={"slug": "codir", "name": "Codir"})
    client.post(BASE, json={"slug": "arbitres", "name": "Arbitres"})

    body = client.get(BASE).json()

    assert [group["slug"] for group in body] == ["arbitres", "codir"]
    assert all(group["member_count"] == 0 for group in body)
    assert "members" not in body[0]


def test_the_detail_names_its_members(client, ouvrir_session, group):
    """FR-012 — la capacité qu'aucune agrégation de rôles ne rend proprement."""
    zoe = ouvrir_session(pose_le_cookie=False, nom="Zoé Martin", email="z@exemple.fr")
    alix = ouvrir_session(pose_le_cookie=False, nom="Alix Roux", email="a@exemple.fr")
    ouvrir_session(superutilisateur=True)
    for member in (zoe, alix):
        client.post(f"{BASE}/{group['id']}/members", json={"user_id": member.id})

    body = client.get(f"{BASE}/{group['id']}").json()

    assert [member["display_name"] for member in body["members"]] == [
        "Alix Roux",
        "Zoé Martin",
    ]
    assert body["member_count"] == 2


def test_an_empty_group_returns_an_empty_composition(client, ouvrir_session, group):
    body = client.get(f"{BASE}/{group['id']}").json()

    assert body["members"] == []
    assert body["member_count"] == 0


def test_an_unknown_group_returns_404(client, ouvrir_session):
    ouvrir_session(P.GROUPS_READ)

    assert client.get(f"{BASE}/9999").status_code == 404


@pytest.mark.parametrize("path", [BASE, f"{BASE}/1"])
def test_a_read_refuses_the_anonymous(client, path):
    assert client.get(path).status_code == 401


@pytest.mark.parametrize("path", [BASE, f"{BASE}/1"])
def test_a_read_refuses_a_session_without_privilege(client, ouvrir_session, path):
    ouvrir_session()

    assert client.get(path).status_code == 403


def test_groups_read_alone_passes_both_reads(client, ouvrir_session, group):
    ouvrir_session(P.GROUPS_READ)

    assert client.get(BASE).status_code == 200
    assert client.get(f"{BASE}/{group['id']}").status_code == 200
