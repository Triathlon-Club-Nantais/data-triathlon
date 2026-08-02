"""FR-025 — aucun octet ne part tant que la validation locale n'a pas abouti.

Ce n'est pas une préférence de style. Le limiteur de threads AnyIO est mesuré à
**40** et toutes les routes du projet sont `def` : un retour de parcours qui
ferait deux allers-retours réseau avant de vérifier sa preuve d'origine serait un
levier de déni de service **sur le site public**, actionnable par un anonyme.
"""
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.core.config import get_settings
from app.services.auth import flow, state
from app.services.auth.errors import LoginError
from app.services.auth.idp.github import GithubIdentityProvider


@pytest.fixture
def github_espionne(monkeypatch):
    """Fournisseur GitHub réel, dont le transport **compte** les requêtes."""
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        vues.append(str(request.url))
        raise AssertionError(f"aucune requête ne devait partir : {request.url}")

    from app.services.auth.idp import registry

    provider = GithubIdentityProvider(
        transport_factory=lambda: httpx.MockTransport(handler)
    )
    monkeypatch.setitem(registry.PROVIDERS, "github", provider)
    return vues


def _appel(db, **surcharges):
    arguments = {
        "provider_slug": "github",
        "state_token": None,
        "state_param": None,
        "code": "code-1",
        "error": None,
    }
    arguments.update(surcharges)
    return flow.complete_login(db, **arguments)


def _etat_valide():
    """Jeton d'état signé, et la valeur `state` **lue dans l'URL d'autorisation**.

    Pas par `state.read()` : sur un jeton volontairement expiré, la relecture
    lèverait dès la préparation du test et l'on n'éprouverait plus rien. L'URL
    est de toute façon l'endroit où le navigateur trouve cette valeur.
    """
    url, jeton = flow.start_login("github")
    return jeton, parse_qs(urlparse(url).query)["state"][0]


def test_aucun_reseau_sans_preuve(db_session, github_espionne):
    with pytest.raises(LoginError):
        _appel(db_session)
    assert github_espionne == []


def test_aucun_reseau_sur_une_preuve_alteree(db_session, github_espionne):
    jeton, valeur = _etat_valide()
    entete, charge, signature = jeton.split(".")

    with pytest.raises(LoginError):
        _appel(db_session, state_token=f"{entete}.{charge}.xxx", state_param=valeur)
    assert github_espionne == []


def test_aucun_reseau_sur_une_preuve_expiree(db_session, github_espionne, monkeypatch):
    # Le TTL est posé **avant** la signature : l'expiration est inscrite dans le
    # jeton, pas relue à chaud. Raccourcir le réglage après coup ne périme aucun
    # jeton déjà émis — c'est d'ailleurs ce qui rend une rotation de réglage
    # sans effet sur les parcours en cours.
    monkeypatch.setenv("AUTH_STATE_TTL_SECONDS", "-1")
    get_settings.cache_clear()
    jeton, valeur = _etat_valide()

    with pytest.raises(LoginError):
        _appel(db_session, state_token=jeton, state_param=valeur)
    assert github_espionne == []


def test_aucun_reseau_sur_un_state_qui_ne_correspond_pas(db_session, github_espionne):
    jeton, _ = _etat_valide()

    with pytest.raises(LoginError):
        _appel(db_session, state_token=jeton, state_param="autre")
    assert github_espionne == []


def test_aucun_reseau_sur_un_autre_fournisseur(db_session, github_espionne, doublure):
    _, jeton = flow.start_login("doublure")
    valeur = state.read(jeton).state

    with pytest.raises(LoginError):
        _appel(db_session, state_token=jeton, state_param=valeur)
    assert github_espionne == []


def test_aucun_reseau_sans_code(db_session, github_espionne):
    jeton, valeur = _etat_valide()

    with pytest.raises(LoginError):
        _appel(db_session, state_token=jeton, state_param=valeur, code=None)
    assert github_espionne == []


def test_aucun_reseau_sur_un_refus_de_consentement(db_session, github_espionne):
    jeton, valeur = _etat_valide()

    with pytest.raises(LoginError):
        _appel(
            db_session,
            state_token=jeton,
            state_param=valeur,
            code=None,
            error="access_denied",
        )
    assert github_espionne == []


def test_authorize_ne_fait_aucune_sortie_reseau(github_espionne):
    """L'entrée du parcours est **gratuite** : c'est ce qui la rend inoffensive
    entre les mains d'un anonyme qui la boucle."""
    flow.start_login("github")

    assert github_espionne == []
