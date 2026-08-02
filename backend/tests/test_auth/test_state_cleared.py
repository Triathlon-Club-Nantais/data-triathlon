"""FR-023 — le cookie d'état est effacé sur **tous** les chemins de sortie.

Succès compris. C'est ce qui donne l'usage unique sans table, sans verrou et sans
purge : le second passage n'a plus rien à présenter.
"""
import pytest

from app.api.v1.auth import state_cookie_name
from app.core.config import get_settings
from app.services.auth import state
from app.services.auth.idp.base import ExternalIdentity


def _demarre(client) -> str:
    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    return state.read(client.cookies[state_cookie_name(get_settings())]).state


def _efface(reponse, nom: str) -> bool:
    entetes = [e for e in reponse.headers.get_list("set-cookie") if e.startswith(f"{nom}=")]
    return bool(entetes) and ("Max-Age=0" in entetes[0] or "1970" in entetes[0])


def _cas_de_sortie(client, doublure):
    """Un couple (intitulé, réponse) par chemin de sortie du callback."""
    valeur = _demarre(client)
    yield (
        "succès",
        client.get(
            f"/api/v1/auth/doublure/callback?code=c&state={valeur}", follow_redirects=False
        ),
    )

    valeur = _demarre(client)
    yield (
        "state ne correspondant pas",
        client.get(
            "/api/v1/auth/doublure/callback?code=c&state=autre", follow_redirects=False
        ),
    )

    valeur = _demarre(client)
    yield (
        "sans code",
        client.get(
            f"/api/v1/auth/doublure/callback?state={valeur}", follow_redirects=False
        ),
    )

    valeur = _demarre(client)
    yield (
        "refus du fournisseur",
        client.get(
            f"/api/v1/auth/doublure/callback?error=access_denied&state={valeur}",
            follow_redirects=False,
        ),
    )

    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="9", email="intrus@exemple.fr",
        email_verified=True, display_name="x",
    )
    valeur = _demarre(client)
    yield (
        "adresse hors liste",
        client.get(
            f"/api/v1/auth/doublure/callback?code=c&state={valeur}", follow_redirects=False
        ),
    )

    doublure.identite = ExternalIdentity(
        provider=doublure.slug, subject="9", email="contributeur@exemple.fr",
        email_verified=False, display_name="x",
    )
    valeur = _demarre(client)
    yield (
        "adresse non certifiée",
        client.get(
            f"/api/v1/auth/doublure/callback?code=c&state={valeur}", follow_redirects=False
        ),
    )


def test_le_cookie_d_etat_est_efface_sur_tous_les_chemins(client, doublure):
    nom = state_cookie_name(get_settings())

    for intitule, reponse in _cas_de_sortie(client, doublure):
        assert _efface(reponse, nom), f"état non effacé : {intitule}"


def test_le_cookie_d_etat_ne_subsiste_pas_dans_le_navigateur(client, doublure):
    valeur = _demarre(client)

    client.get(
        f"/api/v1/auth/doublure/callback?code=c&state={valeur}", follow_redirects=False
    )

    assert state_cookie_name(get_settings()) not in client.cookies


@pytest.mark.parametrize("code", ["c", None])
def test_un_second_parcours_repart_d_un_etat_neuf(client, doublure, code):
    """Scénario 5 d'US3 : rien de l'échec précédent n'empêche de recommencer."""
    premier = _demarre(client)
    client.get(
        f"/api/v1/auth/doublure/callback?state={premier}"
        + (f"&code={code}" if code else ""),
        follow_redirects=False,
    )

    second = _demarre(client)
    reponse = client.get(
        f"/api/v1/auth/doublure/callback?code=c&state={second}", follow_redirects=False
    )

    assert second != premier
    assert "error=" not in reponse.headers["location"]
