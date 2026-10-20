"""`GET /api/v1/auth/methods` — source unique de l'écran de connexion (FR-031)."""
from app.core.config import get_settings

URL = "/api/v1/auth/methods"


def test_les_methodes_configurees_sont_rendues(client):
    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == [{"slug": "github", "label": "GitHub", "audience": "admin"}]


def test_github_is_an_admin_method(client):
    assert client.get(URL).json() == [
        {"slug": "github", "label": "GitHub", "audience": "admin"}
    ]


def test_a_provider_without_audience_is_listed_as_member(client, doublure):
    response = client.get(URL)

    assert response.status_code == 200
    by_slug = {method["slug"]: method for method in response.json()}
    assert by_slug["doublure"]["audience"] == "member"


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

    Depuis #1322 la liste ne conditionne plus du tout la connexion : un compte
    hors liste naît sans rôle, et ce sont les gardes (pouvoir, code du site)
    qui ferment.
    """
    vider_la_liste_autorisation()

    reponse = client.get(URL)

    assert reponse.status_code == 200
    assert reponse.json() == [{"slug": "github", "label": "GitHub", "audience": "admin"}]


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

    assert settings.auth_github_client_secret.get_secret_value() not in corps
    assert settings.auth_github_client_id not in corps
    assert "exemple.fr" not in corps


def test_une_doublure_enregistree_apparait_dans_les_methodes(client, doublure):
    """SC-011 : l'écran de connexion se construit depuis le registre, pas d'une liste."""
    slugs = [methode["slug"] for methode in client.get(URL).json()]

    assert slugs == ["doublure", "github"]
