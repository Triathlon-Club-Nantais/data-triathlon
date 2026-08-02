"""Fournisseur GitHub — URL d'autorisation, échange de jeton, lecture d'identité.

Aucun réseau : le transport du client OAuth est un `httpx.MockTransport`, injecté
par la même couture que le transport gardé de production (`transport=` descend
au constructeur d'`httpx.Client`, dont `OAuth2Client` hérite).
"""
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from app.services.auth.errors import LoginError
from app.services.auth.idp.github import GithubIdentityProvider

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _charge(nom: str):
    return json.loads((FIXTURES / nom).read_text(encoding="utf-8"))


def _provider(handler) -> GithubIdentityProvider:
    return GithubIdentityProvider(transport_factory=lambda: httpx.MockTransport(handler))


def _handler_nominal(user_fixture="github_user_avec_email.json", vues=None):
    def handler(request: httpx.Request) -> httpx.Response:
        if vues is not None:
            vues.append(str(request.url))
        chemin = request.url.path
        if chemin == "/login/oauth/access_token":
            return httpx.Response(200, json=_charge("github_access_token.json"))
        if chemin == "/user":
            return httpx.Response(200, json=_charge(user_fixture))
        if chemin == "/user/emails":
            return httpx.Response(200, json=_charge("github_user_emails.json"))
        raise AssertionError(f"route inattendue : {request.url}")

    return handler


def test_l_url_d_autorisation_porte_state_et_pkce():
    """Sans `code_challenge_method="S256"`, Authlib ignore **silencieusement** le
    `code_verifier` et n'émet aucun `code_challenge` (sondage §3, mesuré)."""
    demande = _provider(_handler_nominal()).authorize(state="etat-123")

    params = parse_qs(urlparse(demande.url).query)
    assert urlparse(demande.url).netloc == "github.com"
    assert params["state"] == ["etat-123"]
    assert params["code_challenge_method"] == ["S256"]
    assert params["code_challenge"]
    assert "code_verifier" not in params  # le vérifieur ne voyage jamais à l'aller


def test_l_aller_retour_porte_le_verifieur():
    demande = _provider(_handler_nominal()).authorize(state="etat-123")

    assert set(demande.round_trip) == {"verifier"}
    assert len(demande.round_trip["verifier"]) >= 43


def test_deux_parcours_n_ont_pas_le_meme_verifieur():
    provider = _provider(_handler_nominal())
    premier = provider.authorize(state="a").round_trip["verifier"]
    second = provider.authorize(state="b").round_trip["verifier"]

    assert premier != second


def test_l_identite_est_lue_sur_l_adresse_publique():
    """Chemin nominal : `/user` suffit, aucun second appel n'est fait."""
    vues: list[str] = []
    provider = _provider(_handler_nominal(vues=vues))

    identite = provider.fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert identite.provider == "github"
    assert identite.subject == "583231"
    assert identite.email == "contributeur@exemple.fr"
    assert identite.email_verified is True
    assert identite.display_name == "contributeur"
    assert not any("/user/emails" in url for url in vues)


def test_le_subject_est_une_chaine():
    """Stocké en `str` : un entier déborderait sur certains dialectes."""
    identite = _provider(_handler_nominal()).fetch_identity(
        code="code-1", round_trip={"verifier": "v" * 43}
    )
    assert isinstance(identite.subject, str)


def test_l_absence_d_adresse_publique_declenche_le_repli():
    """GitHub masque l'adresse par défaut : c'est le cas majoritaire."""
    vues: list[str] = []
    provider = _provider(
        _handler_nominal(user_fixture="github_user_sans_email.json", vues=vues)
    )

    identite = provider.fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert any(url.endswith("/user/emails") for url in vues)
    assert identite.email == "contributeur@exemple.fr"
    assert identite.email_verified is True


def test_le_repli_retient_l_adresse_verifiee_et_primaire():
    """Ni « la première », ni « la primaire » seule : la fixture porte une
    adresse primaire vérifiée, une non vérifiée, et une `noreply` vérifiée."""
    identite = _provider(
        _handler_nominal(user_fixture="github_user_sans_email.json")
    ).fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert identite.email == "contributeur@exemple.fr"


def test_une_adresse_non_verifiee_n_est_jamais_certifiee():
    """FR-005 : `verified` décide, jamais `primary`."""
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json=_charge("github_access_token.json"))
        if request.url.path == "/user":
            return httpx.Response(200, json=_charge("github_user_sans_email.json"))
        return httpx.Response(
            200,
            json=[{"email": "seule@exemple.fr", "primary": True, "verified": False}],
        )

    identite = _provider(handler).fetch_identity(
        code="code-1", round_trip={"verifier": "v" * 43}
    )

    assert identite.email_verified is False


def test_l_echange_de_jeton_ne_suit_aucune_redirection():
    """httpx réémet le corps sur un 307/308, et ce corps porte le `client_secret`.

    Ce que le test prouve est l'**absence** de seconde requête : le corps ne
    repart jamais vers la cible du `Location`. Le refus qui s'ensuit est
    `provider_error` — une 307 sans jeton est une réponse inexploitable au sens
    du contrat, pas un fournisseur injoignable.
    """
    vues: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        vues.append(str(request.url))
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(307, headers={"Location": "https://ailleurs.exemple/token"})
        return httpx.Response(200, json=_charge("github_user_avec_email.json"))

    with pytest.raises(LoginError) as refus:
        _provider(handler).fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_error"
    assert not any("ailleurs.exemple" in url for url in vues)


def test_un_fournisseur_injoignable_rend_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("injoignable")

    with pytest.raises(LoginError) as refus:
        _provider(handler).fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_unavailable"


def test_une_reponse_inexploitable_rend_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json=_charge("github_access_token.json"))
        return httpx.Response(200, json={"pas": "un utilisateur"})

    with pytest.raises(LoginError) as refus:
        _provider(handler).fetch_identity(code="code-1", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_error"


def test_un_code_refuse_par_github_rend_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"error": "bad_verification_code", "error_description": "…"}
        )

    with pytest.raises(LoginError) as refus:
        _provider(handler).fetch_identity(code="mauvais", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_error"


def test_le_fournisseur_n_est_pas_configure_sans_secrets(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("AUTH_GITHUB_CLIENT_ID", "")
    get_settings.cache_clear()

    assert GithubIdentityProvider().is_configured() is False


def test_le_transport_par_defaut_est_le_transport_garde():
    """FR-039 / SC-009 : le trafic OAuth passe par le contrôle de destination (#101).

    Le détecteur AST de `test_core_http.py` interdit déjà un `OAuth2Client` nu
    dans `app/` ; ce test-ci vérifie le pendant positif — la fabrique employée
    est bien celle qui garde.
    """
    from app.core import http

    assert GithubIdentityProvider()._transport_factory is http.guarded_transport
