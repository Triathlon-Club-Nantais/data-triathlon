"""Échecs venant du fournisseur — refus de consentement, panne, réponse illisible."""
import httpx
import pytest

from app.services.auth import flow, state
from app.services.auth.errors import LoginError
from app.services.auth.idp.github import GithubIdentityProvider


def test_un_refus_de_consentement_rend_provider_error(db_session, doublure):
    """L'utilisateur a cliqué « Cancel » : GitHub revient avec `error`, sans code."""
    _, jeton_etat = flow.start_login(doublure.slug)
    charge = state.read(jeton_etat)

    with pytest.raises(LoginError) as refus:
        flow.complete_login(
            db_session,
            provider_slug=doublure.slug,
            state_token=jeton_etat,
            state_param=charge.state,
            code=None,
            error="access_denied",
        )

    assert refus.value.code == "provider_error"
    assert doublure.appels == []


def test_le_message_du_fournisseur_n_atteint_jamais_l_url(client, doublure):
    """FR-028 : aucune donnée d'entrée ne franchit la frontière.

    La correction du défaut de #159 — une page JSON brute — ne doit pas ouvrir
    une injection dans la page de connexion.
    """
    reponse = client.get(
        "/api/v1/auth/doublure/callback"
        "?error=access_denied&error_description=<script>alert(1)</script>",
        follow_redirects=False,
    )

    destination = reponse.headers["location"]
    assert destination.endswith("/login?error=state_mismatch")
    assert "script" not in destination
    assert "access_denied" not in destination


def test_un_fournisseur_injoignable_rend_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("délai dépassé")

    provider = GithubIdentityProvider(
        transport_factory=lambda: httpx.MockTransport(handler)
    )

    with pytest.raises(LoginError) as refus:
        provider.fetch_identity(code="c", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_unavailable"


def test_une_reponse_inexploitable_rend_provider_error():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "x", "token_type": "bearer"})
        return httpx.Response(200, text="<html>maintenance</html>")

    provider = GithubIdentityProvider(
        transport_factory=lambda: httpx.MockTransport(handler)
    )

    with pytest.raises(LoginError) as refus:
        provider.fetch_identity(code="c", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_error"


def test_une_erreur_5xx_du_fournisseur_rend_provider_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/login/oauth/access_token":
            return httpx.Response(200, json={"access_token": "x", "token_type": "bearer"})
        return httpx.Response(503, json={"message": "indisponible"})

    provider = GithubIdentityProvider(
        transport_factory=lambda: httpx.MockTransport(handler)
    )

    with pytest.raises(LoginError) as refus:
        provider.fetch_identity(code="c", round_trip={"verifier": "v" * 43})

    assert refus.value.code == "provider_unavailable"


def test_une_panne_du_fournisseur_n_affecte_pas_le_site_public(client, doublure, monkeypatch):
    """Edge case de la spec : le site public n'est jamais entraîné par un échec."""
    def tombe(**_):
        raise httpx.ConnectError("injoignable")

    monkeypatch.setattr(doublure, "fetch_identity", tombe)

    from app.core.config import get_settings

    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    from app.api.v1.auth import state_cookie_name

    charge = state.read(client.cookies[state_cookie_name(get_settings())])
    echec = client.get(
        f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
        follow_redirects=False,
    )

    assert echec.status_code == 302
    assert "/login?error=" in echec.headers["location"]
    assert client.get("/api/v1/courses").status_code == 200
