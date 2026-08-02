"""`authorize` et `callback` — le parcours vu depuis HTTP."""
from app.core.config import get_settings
from app.models.user import User
from app.services.auth import session, state


def _authorize(client, slug="doublure"):
    return client.get(f"/api/v1/auth/{slug}/authorize", follow_redirects=False)


def _state_cookie(client) -> str:
    from app.api.v1.auth import state_cookie_name

    return client.cookies[state_cookie_name(get_settings())]


def test_authorize_redirige_vers_le_fournisseur(client, doublure):
    reponse = _authorize(client)

    assert reponse.status_code == 302
    assert reponse.headers["location"].startswith("https://doublure.exemple/authorize")


def test_authorize_pose_le_cookie_d_etat(client, doublure):
    reponse = _authorize(client)

    jeton = _state_cookie(client)
    charge = state.read(jeton)
    assert charge.provider == "doublure"
    assert charge.state in reponse.headers["location"]


def test_authorize_ne_prend_aucun_parametre_de_destination(client, doublure):
    """FR-026 : la redirection ouverte est fermée **par construction**.

    Aucune destination n'est acceptée en entrée : elle vient de la
    configuration, donc il n'y a aucune validation à réussir.
    """
    reponse = client.get(
        "/api/v1/auth/doublure/authorize?next=https://evil.example",
        follow_redirects=False,
    )

    assert reponse.status_code == 302
    assert "evil.example" not in reponse.headers["location"]


def test_authorize_ne_cree_aucune_ligne_en_base(client, doublure, db_session):
    from app.models.user_session import UserSession

    _authorize(client)

    assert db_session.query(UserSession).count() == 0
    assert db_session.query(User).count() == 0


def test_authorize_sur_un_fournisseur_inconnu_rend_404(client):
    reponse = client.get("/api/v1/auth/inexistant/authorize", follow_redirects=False)

    assert reponse.status_code == 404


def test_le_callback_nominal_ouvre_une_session(client, doublure, db_session):
    from app.api.v1.auth import session_cookie_name, state_cookie_name

    _authorize(client)
    charge = state.read(_state_cookie(client))

    reponse = client.get(
        f"/api/v1/auth/doublure/callback?code=code-1&state={charge.state}",
        follow_redirects=False,
    )

    assert reponse.status_code == 302
    assert reponse.headers["location"] == get_settings().auth_redirect_base_url

    settings = get_settings()
    jeton = client.cookies[session_cookie_name(settings)]
    assert session.resolve(db_session, jeton) is not None
    # Le cookie d'état a été effacé : l'usage est unique.
    assert state_cookie_name(settings) not in client.cookies


def test_le_callback_sans_cookie_d_etat_redirige_vers_login(client, doublure):
    reponse = client.get(
        "/api/v1/auth/doublure/callback?code=code-1&state=inventé",
        follow_redirects=False,
    )

    assert reponse.status_code == 302
    assert reponse.headers["location"].endswith("/login?error=state_mismatch")


def test_le_callback_sur_un_fournisseur_inconnu_rend_404(client):
    reponse = client.get(
        "/api/v1/auth/inexistant/callback?code=x&state=y", follow_redirects=False
    )

    assert reponse.status_code == 404


def test_un_callback_rejoue_est_refuse(client, doublure, db_session):
    """Le cookie d'état ayant été effacé au premier passage, le rejeu échoue."""
    _authorize(client)
    charge = state.read(_state_cookie(client))
    cible = f"/api/v1/auth/doublure/callback?code=code-1&state={charge.state}"

    client.get(cible, follow_redirects=False)
    rejeu = client.get(cible, follow_redirects=False)

    assert rejeu.headers["location"].endswith("/login?error=state_mismatch")
    assert db_session.query(User).count() == 1
