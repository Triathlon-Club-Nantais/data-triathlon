"""FR-018 — aucune réponse portant une identité ne peut être servie à un autre visiteur.

`Cache-Control: no-store` et `Vary: Cookie` sur **toutes** les réponses du
préfixe, y compris les redirections : le retour de parcours traverse la
réindirection de l'interface, et c'est là qu'un cache intermédiaire ferait le
plus de dégâts — le `Set-Cookie` d'une session servi à quelqu'un d'autre.
"""
import pytest

from app.api.v1.auth import session_cookie_name
from app.core.config import get_settings
from app.repositories import user_repository
from app.services.auth import session, state


def _toutes_les_reponses(client, db_session, doublure):
    """Une réponse par endpoint et par forme de sortie, redirections comprises."""
    reponses = [
        ("methods", client.get("/api/v1/auth/methods")),
        ("logout anonyme", client.post("/api/v1/auth/logout")),
        ("me anonyme", client.get("/api/v1/auth/me")),
        (
            "authorize inconnu",
            client.get("/api/v1/auth/inexistant/authorize", follow_redirects=False),
        ),
        (
            "callback en échec",
            client.get(
                "/api/v1/auth/doublure/callback?code=c&state=faux", follow_redirects=False
            ),
        ),
    ]

    authorize = client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    reponses.append(("authorize", authorize))
    charge = state.read(client.cookies[_state_cookie_name()])
    reponses.append(
        (
            "callback nominal",
            client.get(
                f"/api/v1/auth/doublure/callback?code=c&state={charge.state}",
                follow_redirects=False,
            ),
        )
    )

    user = user_repository.create(db_session, email="a@exemple.fr", display_name="a")
    db_session.flush()
    client.cookies.set(session_cookie_name(get_settings()), session.open_for(db_session, user))
    db_session.commit()
    reponses.append(("me connecté", client.get("/api/v1/auth/me")))
    reponses.append(("logout connecté", client.post("/api/v1/auth/logout")))
    return reponses


def _state_cookie_name() -> str:
    from app.api.v1.auth import state_cookie_name

    return state_cookie_name(get_settings())


def test_toutes_les_reponses_portent_no_store_et_vary(client, db_session, doublure):
    for intitule, reponse in _toutes_les_reponses(client, db_session, doublure):
        assert reponse.headers.get("cache-control") == "no-store", intitule
        assert reponse.headers.get("vary") == "Cookie", intitule


def test_les_en_tetes_ne_sont_pas_poses_endpoint_par_endpoint():
    """Une seule définition : la dépendance de router, et le constructeur de
    redirection qui reprend **les mêmes** valeurs — FastAPI ne fusionnant pas
    les en-têtes d'une dépendance dans une `Response` retournée directement
    (mesuré). Deux points d'application, une seule table de valeurs."""
    import inspect

    from app.api.v1 import auth

    source = inspect.getsource(auth)
    assert source.count('"no-store"') == 1


@pytest.mark.parametrize("chemin", ["/api/v1/courses", "/api/v1/health"])
def test_les_routes_publiques_ne_sont_pas_affectees(client, chemin):
    """L'invariant est **borné** au préfixe d'authentification : poser `no-store`
    sur le site public coûterait son cache à chaque visiteur anonyme."""
    reponse = client.get(chemin)

    assert reponse.headers.get("cache-control") != "no-store"
