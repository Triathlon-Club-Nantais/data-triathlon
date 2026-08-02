"""`GET /api/v1/auth/methods` — source unique de l'écran de connexion (FR-031)."""
from app.core.config import get_settings

URL = "/api/v1/auth/methods"


def test_les_methodes_configurees_sont_rendues(client):
    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == [{"slug": "github", "label": "GitHub"}]


def test_une_liste_d_autorisation_vide_ne_propose_aucune_methode(client, monkeypatch):
    """FR-007 : sans compte autorisé, aucune connexion ne peut aboutir.

    Proposer un bouton mènerait à un refus systématique — la liste vide **est**
    la réponse juste, et l'interface l'affiche comme telle.
    """
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    get_settings.cache_clear()

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_une_authentification_non_configuree_ne_propose_aucune_methode(client, monkeypatch):
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_ID", "")
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_SECRET", "")
    get_settings.cache_clear()

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_l_endpoint_ne_revele_aucun_secret(client):
    """Jamais authentifié, et ne divulgue ni identifiant client ni adresse."""
    settings = get_settings()
    corps = client.get(URL).text

    assert settings.auth_github_client_secret not in corps
    assert settings.auth_github_client_id not in corps
    assert "exemple.fr" not in corps


def test_une_doublure_enregistree_apparait_dans_les_methodes(client, doublure):
    """SC-011 : l'écran de connexion se construit depuis le registre, pas d'une liste."""
    slugs = [methode["slug"] for methode in client.get(URL).json()]

    assert slugs == ["doublure", "github"]
