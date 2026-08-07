"""`GET /api/v1/auth/methods` — source unique de l'écran de connexion (FR-031)."""
from app.core.config import get_settings

URL = "/api/v1/auth/methods"


def test_les_methodes_configurees_sont_rendues(client):
    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == [{"slug": "github", "label": "GitHub"}]


def test_la_liste_d_autorisation_n_est_pas_interrogee(
    client, vider_la_liste_autorisation
):
    """FR-011 de #170 : cette route n'interroge **aucune** table.

    Elle rendait `[]` quand la liste d'autorisation était vide, du temps où
    celle-ci était un réglage. La liste vit maintenant en base, et la faire peser
    ici transformerait une route **publique et non authentifiée** — appelée par
    la page de connexion — en requête base. Le limiteur de threads AnyIO est
    mesuré à 40 et toutes les routes du projet sont `def` : c'est le levier de
    charge que #114 a fermé sur le retour de parcours.

    Le fail-closed n'est pas perdu, il est déplacé là où il décide :
    `provisioning` refuse en `account_not_allowed`, liste vide comprise.
    """
    vider_la_liste_autorisation()

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == [{"slug": "github", "label": "GitHub"}]


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
