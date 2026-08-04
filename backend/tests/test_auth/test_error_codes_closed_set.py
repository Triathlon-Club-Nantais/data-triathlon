"""FR-028 — `?error=` ne porte **jamais** rien d'autre qu'un code du contrat.

Ni un message du fournisseur, ni une donnée d'entrée. La correction du défaut de
la PR #159 — qui affichait une page JSON brute — ne doit pas ouvrir une injection
dans la page de connexion.
"""
from urllib.parse import parse_qs, urlparse

import pytest

from app.api.v1.auth import state_cookie_name
from app.core.config import get_settings
from app.services.auth import state
from app.services.auth.errors import ERROR_CODES, INTERNAL_CODES, LoginError
from app.services.auth.idp.base import ExternalIdentity

#: Charges hostiles passées telles quelles aux paramètres du callback.
HOSTILES = [
    "<script>alert(1)</script>",
    "https://evil.example/",
    "../../etat",
    "state_mismatch&admin=1",
    "%0d%0aSet-Cookie:%20a=b",
    "'; DROP TABLE users; --",
]


def _code_rendu(reponse) -> str | None:
    destination = urlparse(reponse.headers["location"])
    return parse_qs(destination.query).get("error", [None])[0]


@pytest.mark.parametrize("charge", HOSTILES)
def test_aucune_donnee_d_entree_n_atteint_le_parametre(client, doublure, charge):
    reponse = client.get(
        "/api/v1/auth/doublure/callback",
        params={"code": charge, "state": charge, "error": charge},
        follow_redirects=False,
    )

    code = _code_rendu(reponse)
    assert code in ERROR_CODES
    assert charge not in reponse.headers["location"]


def test_tous_les_chemins_d_echec_rendent_un_code_du_contrat(client, doublure):
    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="9", email="intrus@exemple.fr",
        email_verified=True, display_name="x",
    )
    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    valeur = state.read(client.cookies[state_cookie_name(get_settings())]).state

    reponse = client.get(
        f"/api/v1/auth/doublure/callback?code=c&state={valeur}", follow_redirects=False
    )

    assert _code_rendu(reponse) == "account_not_allowed"


def test_un_code_interne_ne_franchit_jamais_la_frontiere():
    """`unknown_provider` et `not_configured` sont des états **internes** : les
    laisser sortir mettrait une valeur non contractuelle dans une URL publique,
    que l'interface ne saurait pas traduire."""
    from app.api.v1.auth import _failure_redirect

    settings = get_settings()
    for interne in INTERNAL_CODES:
        destination = _failure_redirect(interne, settings).headers["location"]
        assert parse_qs(urlparse(destination).query)["error"][0] in ERROR_CODES


def test_l_ensemble_des_codes_est_ferme_a_la_construction():
    """Un code hors contrat ne peut pas être levé : l'erreur est immédiate,
    plutôt qu'une valeur inconnue découverte en production dans une URL."""
    with pytest.raises(ValueError):
        raise LoginError("code_invente")


def test_les_cinq_codes_du_contrat_sont_exactement_ceux_ci():
    assert ERROR_CODES == {
        "state_mismatch",
        "email_unverified",
        "account_not_allowed",
        "provider_error",
        "provider_unavailable",
    }
