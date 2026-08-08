"""Tests de la configuration centralisée (`app.core.config`)."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_cors_origins_csv_depuis_env(monkeypatch):
    """CORS_ORIGINS en CSV (format Render) doit être parsé en liste.

    Non-régression : pydantic-settings tentait de décoder la valeur en JSON
    avant le validateur et levait une SettingsError. Le marqueur NoDecode
    laisse la chaîne brute arriver jusqu'à `_split_cors`.
    """
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app,https://b.com")
    assert Settings().cors_origins == ["https://a.vercel.app", "https://b.com"]


def test_cors_origins_valeur_unique(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://a.vercel.app")
    assert Settings().cors_origins == ["https://a.vercel.app"]


def test_cors_origins_csv_avec_espaces(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", " https://a.vercel.app , https://b.com ")
    assert Settings().cors_origins == ["https://a.vercel.app", "https://b.com"]


def test_cors_origins_defaut(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    assert "http://localhost:3000" in Settings().cors_origins


def test_observabilite_sql_defauts(monkeypatch):
    """Défauts : seuil à 100 ms, bilan éteint.

    Le bilan est éteint par défaut parce qu'il coûte ; le seuil, lui, est le
    garde-fou permanent.
    """
    for var in ("SQL_SLOW_QUERY_MS", "SQL_QUERY_STATS"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.sql_slow_query_ms == 100
    assert settings.sql_query_stats is False


def test_observabilite_sql_depuis_env(monkeypatch):
    monkeypatch.setenv("SQL_SLOW_QUERY_MS", "250")
    monkeypatch.setenv("SQL_QUERY_STATS", "true")
    settings = Settings()
    assert settings.sql_slow_query_ms == 250
    assert settings.sql_query_stats is True


# ── Socle d'authentification (#114) ───────────────────────────────────────────
#
# `Settings` lit `.env` : chaque test pose explicitement ce qu'il éprouve, sans
# quoi un développeur ayant de vrais secrets locaux verrait ces tests passer
# pour la mauvaise raison.






def test_une_cle_de_signature_trop_courte_est_refusee(monkeypatch):
    """FR-037 : le démarrage échoue plutôt que de signer avec 8 caractères."""
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "trop-court")
    with pytest.raises(ValidationError):
        Settings()


def test_une_cle_de_signature_de_32_caracteres_est_acceptee(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "x" * 32)
    assert Settings().auth_session_secret_key == "x" * 32


def test_l_origine_de_retour_perd_son_slash_final(monkeypatch):
    """Trois sites concatènent cette origine ; le plus fragile n'est pas `/admin`.

    `…//admin` reste navigable, mais le `redirect_uri` envoyé au fournisseur ne
    correspondrait plus à celui enregistré chez lui : le parcours entier
    échouerait chez GitHub. La valeur est saisie à la main sur Render
    (`sync: false`), donc le slash final est un cas ordinaire.
    """
    monkeypatch.setenv("AUTH_REDIRECT_BASE_URL", "https://exemple.fr/")
    assert Settings().auth_redirect_base_url == "https://exemple.fr"


def test_une_origine_de_retour_vide_le_reste(monkeypatch):
    """Vide vaut « non configuré » (FR-036) : la normalisation ne la ranime pas."""
    monkeypatch.setenv("AUTH_REDIRECT_BASE_URL", "/")
    assert Settings().auth_redirect_base_url == ""


def test_une_cle_de_signature_vide_vaut_non_configure(monkeypatch):
    """Une installation sans authentification doit démarrer (FR-036).

    C'est la distinction structurante : **vide** signifie « pas d'authentification
    sur ce site », et le site public reste intact ; **court** signifie « clé
    faible », et c'est un défaut de configuration qu'on refuse.
    """
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "")
    assert Settings().auth_session_secret_key == ""
