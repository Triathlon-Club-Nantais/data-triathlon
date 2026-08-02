"""SC-004 — toutes les formes d'atteinte à la preuve d'origine sont refusées.

Un **seul** code pour toutes : distinguer « expirée » de « altérée » ne
renseignerait qu'un attaquant.
"""
import pytest

from app.core.config import get_settings
from app.services.auth import flow, state
from app.services.auth.errors import LoginError


def _parcours(db, slug="doublure", **surcharges):
    _, jeton_etat = flow.start_login(slug)
    charge = state.read(jeton_etat)
    arguments = {
        "provider_slug": slug,
        "state_token": jeton_etat,
        "state_param": charge.state,
        "code": "code-1",
        "error": None,
    }
    arguments.update(surcharges)
    return flow.complete_login(db, **arguments)


def test_preuve_absente(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, state_token=None)
    assert refus.value.code == "state_mismatch"


def test_preuve_vide(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, state_token="")
    assert refus.value.code == "state_mismatch"


def test_preuve_alteree(db_session, doublure):
    _, jeton = flow.start_login("doublure")
    entete, charge, signature = jeton.split(".")

    with pytest.raises(LoginError) as refus:
        _parcours(db_session, state_token=f"{entete}.{charge}.{signature[:-3]}xyz")
    assert refus.value.code == "state_mismatch"


def test_preuve_expiree(db_session, doublure, monkeypatch):
    monkeypatch.setenv("AUTH_STATE_TTL_SECONDS", "-1")
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        _parcours(db_session)
    assert refus.value.code == "state_mismatch"


def test_state_ne_correspondant_pas(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, state_param="autre-chose")
    assert refus.value.code == "state_mismatch"


def test_state_absent_de_l_url(db_session, doublure):
    with pytest.raises(LoginError) as refus:
        _parcours(db_session, state_param=None)
    assert refus.value.code == "state_mismatch"


def test_preuve_rejouee(client, doublure):
    """Le rejeu est fermé par l'**effacement** du cookie, pas par une table.

    C'est ce qui donne l'usage unique sans verrou : le second passage n'a plus
    de cookie d'état à présenter.
    """
    from app.api.v1.auth import state_cookie_name

    client.get("/api/v1/auth/doublure/authorize", follow_redirects=False)
    charge = state.read(client.cookies[state_cookie_name(get_settings())])
    cible = f"/api/v1/auth/doublure/callback?code=c&state={charge.state}"

    premier = client.get(cible, follow_redirects=False)
    second = client.get(cible, follow_redirects=False)

    assert "error=" not in premier.headers["location"]
    assert second.headers["location"].endswith("/login?error=state_mismatch")


def test_preuve_emise_pour_un_autre_fournisseur(db_session, doublure):
    """FR-022 — la confusion de fournisseur, fermée par le `provider` signé."""
    _, jeton_github = flow.start_login("github")
    charge = state.read(jeton_github)

    with pytest.raises(LoginError) as refus:
        flow.complete_login(
            db_session,
            provider_slug="doublure",
            state_token=jeton_github,
            state_param=charge.state,
            code="code-1",
            error=None,
        )
    assert refus.value.code == "state_mismatch"


def test_preuve_signee_avec_une_autre_cle(db_session, doublure, monkeypatch):
    _, jeton = flow.start_login("doublure")
    charge = state.read(jeton)

    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "z" * 48)
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        flow.complete_login(
            db_session,
            provider_slug="doublure",
            state_token=jeton,
            state_param=charge.state,
            code="code-1",
            error=None,
        )
    assert refus.value.code == "state_mismatch"
