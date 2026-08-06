"""`GET /auth/me` rend les groupes du porteur (#197, AC4).

Le champ s'ajoute à côté de `permissions` et `roles`, posés par #115 au même
endroit et pour la même raison : une interface doit pouvoir écrire « membre du
Codir » sans un second appel, que `GET /admin/groups` refuserait justement à qui
n'a pas `groups:read`.

**Il ne dit rien des droits.** `permissions` répond à « ai-je le droit d'afficher
ce bouton » ; les confondre ferait entrer les groupes dans la décision d'accès
côté interface, ce que l'AC6 refuse côté serveur.
"""
from app.repositories import group_repository

ME = "/api/v1/auth/me"

#: Les clés du contrat, avant #197. Écrites à la main : c'est ce qui prouve
#: l'additivité au sens du Principe IV — aucun champ retiré, aucune sémantique
#: inversée, aucun code de retour modifié.
KEYS_BEFORE_197 = {
    "id",
    "email",
    "display_name",
    "created_at",
    "permissions",
    "roles",
}


def _join(db_session, organisation, member, slug: str):
    group = group_repository.create(
        db_session, organisation_id=organisation.id, slug=slug, name=slug.title()
    )
    group_repository.add_member(db_session, group_id=group.id, user_id=member.id)
    db_session.commit()
    return group


def test_the_session_returns_its_bearer_groups(
    client, db_session, ouvrir_session, organisation
):
    member = ouvrir_session()
    _join(db_session, organisation, member, "codir")
    _join(db_session, organisation, member, "arbitres")

    body = client.get(ME).json()

    assert sorted(group["slug"] for group in body["groups"]) == ["arbitres", "codir"]
    assert body["groups"][0]["organisation_id"] == organisation.id
    assert {"id", "slug", "name", "organisation_id"} == set(body["groups"][0])


def test_without_membership_the_field_is_empty(client, ouvrir_session):
    """État normal — celui de tout le monde sur une installation neuve."""
    ouvrir_session()

    assert client.get(ME).json()["groups"] == []


def test_reading_oneself_requires_no_privilege(
    client, db_session, ouvrir_session, organisation
):
    """Contrepartie de `GET /admin/groups`, qui exige `groups:read` : celle-ci ne
    porte que sur soi."""
    member = ouvrir_session()
    _join(db_session, organisation, member, "codir")

    response = client.get(ME)

    assert response.status_code == 200
    assert response.json()["permissions"] == []
    assert [group["slug"] for group in response.json()["groups"]] == ["codir"]


def test_the_new_field_is_strictly_additive(client, ouvrir_session):
    """Principe IV — un consommateur existant ne voit rien changer."""
    ouvrir_session()

    keys = set(client.get(ME).json())

    assert KEYS_BEFORE_197 < keys
    assert keys - KEYS_BEFORE_197 == {"groups"}


def test_a_removal_shows_on_the_next_request_without_reconnecting(
    client, db_session, ouvrir_session, organisation
):
    """La décision est relue à chaque requête, ici comme pour les pouvoirs.

    Retirer quelqu'un d'un groupe **n'invalide pas sa session** : rien de ce
    qu'il peut faire n'en dépend, et le déconnecter serait disproportionné.
    """
    member = ouvrir_session()
    group = _join(db_session, organisation, member, "codir")
    assert client.get(ME).json()["groups"] != []

    group_repository.remove_member(db_session, group_id=group.id, user_id=member.id)
    db_session.commit()

    response = client.get(ME)
    assert response.status_code == 200, "la session reste valide"
    assert response.json()["groups"] == []


def test_an_anonymous_visitor_still_gets_401(client):
    """Point de contrat figé par #114 : jamais « 200 vide »."""
    assert client.get(ME).status_code == 401
