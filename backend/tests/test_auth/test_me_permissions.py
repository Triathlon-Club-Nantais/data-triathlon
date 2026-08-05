"""`GET /auth/me` enrichi de ses pouvoirs et de ses rôles (#115, FR-020).

Ajout **additif** : aucun champ existant ne change. La docstring de
`SessionUserRead` (#114) l'annonçait déjà comme non cassant au sens du
Principe IV, qui vise le champ retiré, la sémantique inversée et le code de
retour modifié.
"""
from app.core.permissions import P

CHAMPS_114 = {"id", "email", "display_name", "created_at"}


def test_les_champs_de_114_sont_inchanges(client, ouvrir_session):
    ouvrir_session(P.QUALITY_OVERRIDE, nom="Prénom Nom")

    corps = client.get("/api/v1/auth/me").json()

    assert CHAMPS_114 <= set(corps)
    assert corps["display_name"] == "Prénom Nom"
    assert corps["created_at"].endswith("Z")


def test_me_rend_les_pouvoirs_effectifs_et_les_roles(client, ouvrir_session):
    """Les deux champs sont **nécessaires et ne se déduisent pas l'un de l'autre**.

    `permissions` répond à « ai-je le droit d'afficher ce bouton », `roles` à
    « comment me présenter à moi-même ». Sans le second, écrire « connecté en
    tant qu'administrateur » exige un appel de plus, que `GET /admin/roles`
    refuserait justement à qui n'a pas `roles:read`.
    """
    ouvrir_session(P.QUALITY_OVERRIDE)

    corps = client.get("/api/v1/auth/me").json()

    assert corps["permissions"] == [P.QUALITY_OVERRIDE.code]
    assert len(corps["roles"]) == 1
    assert {"id", "slug", "name", "organisation_id"} == set(corps["roles"][0])


def test_me_n_exige_aucun_pouvoir(client, ouvrir_session):
    """Elle ne porte que sur soi — c'est la contrepartie de FR-003, qui réserve
    l'inventaire **général** des pouvoirs à `roles:read`."""
    ouvrir_session()

    assert client.get("/api/v1/auth/me").status_code == 200


def test_un_connecte_sans_role_obtient_deux_listes_vides_et_non_un_403(
    client, ouvrir_session
):
    """« Connecté sans droit » est un état légitime, pas une erreur.

    C'est même l'état de tout le monde sur une installation neuve.
    """
    ouvrir_session()

    corps = client.get("/api/v1/auth/me").json()

    assert corps["permissions"] == []
    assert corps["roles"] == []


def test_le_meme_compte_recoit_403_sur_l_inventaire_general(client, ouvrir_session):
    """La démonstration que les deux lectures n'ont ni le même objet ni le même prix."""
    ouvrir_session()

    assert client.get("/api/v1/auth/me").status_code == 200
    assert client.get("/api/v1/admin/permissions").status_code == 403


def test_un_superutilisateur_voit_le_catalogue_dans_ses_pouvoirs(client, ouvrir_session):
    from app.core.permissions import CODES

    ouvrir_session(superutilisateur=True)

    assert set(client.get("/api/v1/auth/me").json()["permissions"]) == CODES


def test_me_rend_toujours_401_sans_session(client):
    """Point de contrat **figé** de #114 : jamais « 200 avec un corps nul »."""
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_n_expose_toujours_ni_jeton_ni_identifiant_de_session(client, ouvrir_session):
    ouvrir_session(P.ROLES_READ)

    corps = client.get("/api/v1/auth/me").text

    assert "token" not in corps
    assert "session" not in corps
