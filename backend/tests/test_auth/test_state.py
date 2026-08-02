"""Jeton d'état du parcours de connexion — signature, relecture, rejets (FR-020 à FR-022)."""
import pytest

from app.core.config import get_settings
from app.services.auth import state
from app.services.auth.errors import LoginError


def test_un_etat_signe_se_relit_verbatim():
    jeton = state.sign(provider="github", state="abc123", round_trip={"verifier": "xyz"})

    charge = state.read(jeton)

    assert charge.provider == "github"
    assert charge.state == "abc123"
    assert charge.round_trip == {"verifier": "xyz"}


def test_l_aller_retour_n_est_jamais_interprete():
    """FR-032 : le flux signe et restitue un opaque, il ne le lit pas.

    C'est ce qui permettra à un futur OIDC d'y ranger son `nonce` sans toucher
    ni au contrat, ni au flux, ni au fournisseur GitHub.
    """
    opaque = {"verifier": "xyz", "nonce": "n-1", "quoi_que_ce_soit": "42"}

    charge = state.read(state.sign(provider="oidc", state="s", round_trip=opaque))

    assert charge.round_trip == opaque


def test_un_etat_signe_avec_une_autre_cle_est_rejete(monkeypatch):
    jeton = state.sign(provider="github", state="abc", round_trip={})

    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "z" * 48)
    get_settings.cache_clear()

    with pytest.raises(LoginError) as refus:
        state.read(jeton)
    assert refus.value.code == "state_mismatch"


def test_un_etat_altere_est_rejete():
    jeton = state.sign(provider="github", state="abc", round_trip={})

    entete, charge, signature = jeton.split(".")
    with pytest.raises(LoginError):
        state.read(f"{entete}.{charge}.{signature[:-2]}xx")


def test_un_etat_expire_est_rejete(monkeypatch):
    """La fenêtre est courte (10 min) et c'est elle qui borne le rejeu."""
    monkeypatch.setenv("AUTH_STATE_TTL_SECONDS", "-1")
    get_settings.cache_clear()

    jeton = state.sign(provider="github", state="abc", round_trip={})

    with pytest.raises(LoginError) as refus:
        state.read(jeton)
    assert refus.value.code == "state_mismatch"


def test_un_jeton_qui_n_en_est_pas_un_est_rejete():
    for valeur in ("", "pas-un-jeton", "a.b.c"):
        with pytest.raises(LoginError):
            state.read(valeur)


def test_deux_etats_consecutifs_different():
    """`new_state()` doit être imprévisible — c'est la preuve d'origine (FR-021)."""
    valeurs = {state.new_state() for _ in range(20)}
    assert len(valeurs) == 20
    assert all(len(valeur) >= 32 for valeur in valeurs)
