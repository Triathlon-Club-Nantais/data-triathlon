"""FR-036 — une authentification non configurée n'empêche pas le site de vivre.

Une installation sans secrets OAuth est un **état légitime** : le site public
fonctionne intégralement, et seul le parcours de connexion signale
l'indisponibilité, en français.
"""
import pytest

from app.core.config import get_settings


@pytest.fixture
def non_configure(monkeypatch):
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_ID", "")
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_SECRET", "")
    get_settings.cache_clear()


def test_authorize_rend_503(client, non_configure):
    reponse = client.get("/api/v1/auth/github/authorize", follow_redirects=False)

    assert reponse.status_code == 503


def test_le_message_de_503_est_en_francais(client, non_configure):
    """Clause « Cas mixte — les `DomainError` » du Principe I : ces messages sont
    sérialisés dans `{"detail": …}` et réaffichés verbatim par le front."""
    detail = client.get("/api/v1/auth/github/authorize", follow_redirects=False).json()["detail"]

    assert "authentification" in detail.lower()
    assert not any(mot in detail.lower() for mot in ("error", "not", "unavailable"))


def test_methods_rend_une_liste_vide(client, non_configure):
    reponse = client.get("/api/v1/auth/methods")

    assert reponse.status_code == 200
    assert reponse.json() == []


def test_me_rend_401_et_non_503(client, non_configure):
    """Ne pas être connecté reste un 401, même sans authentification configurée :
    c'est le contrat de l'endpoint, pas une conséquence du déploiement."""
    assert client.get("/api/v1/auth/me").status_code == 401


def test_logout_reste_idempotent(client, non_configure):
    assert client.post("/api/v1/auth/logout").status_code == 204


@pytest.mark.parametrize(
    "chemin",
    ["/api/v1/courses", "/api/v1/athletes", "/api/v1/stats", "/api/v1/health"],
)
def test_le_site_public_est_intact(client, non_configure, chemin):
    assert client.get(chemin).status_code == 200


def test_une_cle_de_signature_absente_ne_casse_pas_le_site(client, monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "")
    get_settings.cache_clear()

    assert client.get("/api/v1/courses").status_code == 200
    assert client.get("/api/v1/auth/methods").json() == []


def test_une_cle_absente_rend_503_et_non_une_page_technique(client, monkeypatch):
    """FR-027 / FR-036 : une configuration partielle ne produit jamais de 500.

    Cas mesuré : clé de signature vide **mais** GitHub configuré. `start_login`
    n'éprouvait alors que la configuration du fournisseur, et `joserfc` levait un
    `ValueError` nu (« oct key material must not be empty ») jusqu'au handler
    global — soit une page d'erreur technique dans un navigateur en pleine
    navigation, exactement ce que le contrat proscrit.
    """
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "")
    get_settings.cache_clear()

    reponse = client.get("/api/v1/auth/github/authorize", follow_redirects=False)

    assert reponse.status_code == 503
    assert "authentification" in reponse.json()["detail"].lower()


def test_une_liste_d_autorisation_vide_ferme_le_parcours(client, monkeypatch):
    """Fail-closed jusqu'au bout : ne pas proposer de méthode ne suffit pas, il
    faut aussi refuser l'entrée du parcours à qui en connaîtrait l'URL."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    get_settings.cache_clear()

    assert client.get("/api/v1/auth/github/authorize", follow_redirects=False).status_code == 503


def test_la_configuration_transverse_ne_depend_d_aucun_fournisseur(client, doublure, monkeypatch):
    """FR-033 : ajouter un fournisseur n'exige de modifier ni le contrat, ni le flux.

    Un garde global qui exigerait les secrets **GitHub** masquerait un second
    fournisseur pourtant configuré — il faudrait alors modifier ce garde à chaque
    ajout, ce que le principe interdit.
    """
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_ID", "")
    monkeypatch.setenv("AUTH_GITHUB_CLIENT_SECRET", "")
    get_settings.cache_clear()

    slugs = [methode["slug"] for methode in client.get("/api/v1/auth/methods").json()]

    assert slugs == ["doublure"]
    assert client.get("/api/v1/auth/doublure/authorize", follow_redirects=False).status_code == 302


def test_une_url_de_retour_absente_vaut_non_configure(client, monkeypatch):
    """Le `redirect_uri` envoyé au fournisseur ne doit jamais retomber sur un défaut.

    Ce réglage part dans le `redirect_uri` enregistré chez GitHub. Avec un
    défaut localhost et aucune garde, un déploiement qui l'oublie paraissait
    **pleinement configuré** — `/auth/methods` listait GitHub, la page de
    connexion affichait son bouton — pendant que GitHub répondait par sa propre
    page « The redirect_uri is not associated with this application ». Le
    visiteur ne revenait jamais, aucun code de l'ensemble fermé ne se
    déclenchait, et rien n'était journalisé côté backend.
    """
    monkeypatch.setenv("AUTH_REDIRECT_BASE_URL", "")
    get_settings.cache_clear()

    assert client.get("/api/v1/auth/methods").json() == []
    assert client.get("/api/v1/auth/github/authorize", follow_redirects=False).status_code == 503
