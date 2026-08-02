"""FR-038 — ni secret, ni jeton, ni paramètre de retour dans les journaux.

Filet de non-régression, comme `test_public_routes_still_open` : il n'y a rien à
faire advenir ici, il doit passer dès le premier jet et le rester. Les journaux
partent vers Sentry/Datadog, où un `client_secret` ou un jeton de session
survivrait bien plus longtemps que dans la mémoire du processus.
"""
import logging

import pytest

from app.api.v1.auth import session_cookie_name, state_cookie_name
from app.core.config import get_settings
from app.services.auth import state
from app.services.auth.idp.base import ExternalIdentity

CODE_DE_RETOUR = "code-secret-de-retour-42"


def _demarre(client) -> str:
    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    return state.read(client.cookies[state_cookie_name(get_settings())]).state


def _valeurs_interdites(client) -> list[str]:
    settings = get_settings()
    interdites = [
        settings.auth_github_client_secret,
        settings.auth_session_secret_key,
        CODE_DE_RETOUR,
    ]
    jeton = client.cookies.get(session_cookie_name(settings))
    if jeton:
        interdites.append(jeton)
    return [valeur for valeur in interdites if valeur]


def _journal_applicatif(caplog) -> str:
    """Journaux émis par `app.*`, à l'exclusion de ceux du bac à sable.

    Le client de test est un client httpx, dont le logger `httpx` trace chaque
    URL appelée — `?code=…` compris. C'est un artefact : en production, cet
    appel vient du navigateur, et personne côté application ne l'écrit.

    Reste, hors du périmètre de ce test comme du code applicatif, le **journal
    d'accès du serveur** : uvicorn trace lui aussi l'URL. Le `code` d'un retour
    de parcours y figure donc, et le neutraliser relève de la configuration de
    déploiement, pas d'`app/` — c'est nommé ici pour qu'on ne croie pas le
    problème réglé par ce seul test.
    """
    return "\n".join(
        enregistrement.getMessage()
        for enregistrement in caplog.records
        if enregistrement.name.startswith("app")
    ) + "\n".join(
        caplog.handler.format(enregistrement)
        for enregistrement in caplog.records
        if enregistrement.name.startswith("app") and enregistrement.exc_info
    )


def _controle(caplog, client, intitule: str) -> None:
    journal = _journal_applicatif(caplog)
    for valeur in _valeurs_interdites(client):
        assert valeur not in journal, f"{intitule} : une valeur sensible est journalisée"


def test_le_parcours_nominal_ne_journalise_aucun_secret(client, doublure, caplog):
    with caplog.at_level(logging.DEBUG):
        valeur = _demarre(client)
        client.get(
            f"/api/v1/auth/doublure/callback?code={CODE_DE_RETOUR}&state={valeur}",
            follow_redirects=False,
        )

    _controle(caplog, client, "succès")


@pytest.mark.parametrize(
    "intitule",
    ["state_mismatch", "sans_code", "refus_fournisseur", "hors_liste", "non_certifiee"],
)
def test_aucun_chemin_d_echec_ne_journalise_de_secret(client, doublure, caplog, intitule):
    if intitule == "hors_liste":
        doublure.identite = ExternalIdentity(
            provider=doublure.slug, subject="9", email="intrus@exemple.fr",
            email_verified=True, display_name="x",
        )
    if intitule == "non_certifiee":
        doublure.identite = ExternalIdentity(
            provider=doublure.slug, subject="9", email="contributeur@exemple.fr",
            email_verified=False, display_name="x",
        )

    with caplog.at_level(logging.DEBUG):
        valeur = _demarre(client)
        cible = {
            "state_mismatch": f"/api/v1/auth/doublure/callback?code={CODE_DE_RETOUR}&state=faux",
            "sans_code": f"/api/v1/auth/doublure/callback?state={valeur}",
            "refus_fournisseur": (
                f"/api/v1/auth/doublure/callback?error=access_denied&state={valeur}"
            ),
            "hors_liste": f"/api/v1/auth/doublure/callback?code={CODE_DE_RETOUR}&state={valeur}",
            "non_certifiee": (
                f"/api/v1/auth/doublure/callback?code={CODE_DE_RETOUR}&state={valeur}"
            ),
        }[intitule]
        client.get(cible, follow_redirects=False)

    _controle(caplog, client, intitule)


def test_une_panne_inattendue_ne_deverse_pas_le_code(client, doublure, caplog, monkeypatch):
    """Le chemin le plus exposé : `logger.exception` rend une trace complète,
    et une trace porte les arguments des cadres qu'elle traverse."""
    def tombe(**_):
        raise RuntimeError("panne interne")

    monkeypatch.setattr(doublure, "fetch_identity", tombe)

    with caplog.at_level(logging.DEBUG):
        valeur = _demarre(client)
        client.get(
            f"/api/v1/auth/doublure/callback?code={CODE_DE_RETOUR}&state={valeur}",
            follow_redirects=False,
        )

    _controle(caplog, client, "panne inattendue")


def test_le_jeton_de_session_n_est_jamais_journalise(client, db_session, caplog):
    from app.repositories import user_repository
    from app.services.auth import session

    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    db_session.flush()
    jeton = session.open_for(db_session, user)
    db_session.commit()
    client.cookies.set(session_cookie_name(get_settings()), jeton)

    with caplog.at_level(logging.DEBUG):
        client.get("/api/v1/auth/me")
        client.post("/api/v1/auth/logout")

    assert jeton not in _journal_applicatif(caplog)
