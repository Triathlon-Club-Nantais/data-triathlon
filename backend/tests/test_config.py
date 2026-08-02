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
    """Défauts : seuil à 100 ms, bilan et OTel éteints.

    Le bilan et OTel sont éteints par défaut parce qu'ils coûtent ; le seuil,
    lui, est le garde-fou permanent.
    """
    for var in ("SQL_SLOW_QUERY_MS", "SQL_QUERY_STATS", "OTEL_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    settings = Settings()
    assert settings.sql_slow_query_ms == 100
    assert settings.sql_query_stats is False
    assert settings.otel_enabled is False


def test_observabilite_sql_depuis_env(monkeypatch):
    monkeypatch.setenv("SQL_SLOW_QUERY_MS", "250")
    monkeypatch.setenv("SQL_QUERY_STATS", "true")
    monkeypatch.setenv("OTEL_ENABLED", "true")
    settings = Settings()
    assert settings.sql_slow_query_ms == 250
    assert settings.sql_query_stats is True
    assert settings.otel_enabled is True


# ── Socle d'authentification (#114) ───────────────────────────────────────────
#
# `Settings` lit `.env` : chaque test pose explicitement ce qu'il éprouve, sans
# quoi un développeur ayant de vrais secrets locaux verrait ces tests passer
# pour la mauvaise raison.


def test_auth_allowed_emails_csv_depuis_env(monkeypatch):
    """Même format que CORS_ORIGINS : CSV, seul format que Render sait poser."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "a@exemple.fr,b@exemple.fr")
    assert Settings().auth_allowed_emails == ["a@exemple.fr", "b@exemple.fr"]


def test_auth_allowed_emails_csv_avec_espaces(monkeypatch):
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", " a@exemple.fr , b@exemple.fr ")
    assert Settings().auth_allowed_emails == ["a@exemple.fr", "b@exemple.fr"]


def test_auth_allowed_emails_vide_est_une_liste_vide(monkeypatch):
    """Fail-closed : vide n'a jamais valu « tout le monde » (FR-007)."""
    monkeypatch.setenv("AUTH_ALLOWED_EMAILS", "")
    assert Settings().auth_allowed_emails == []


def test_auth_allowed_emails_defaut_est_vide(monkeypatch):
    """`_env_file=None` : c'est le défaut du code qu'on éprouve, pas le `.env` local."""
    monkeypatch.delenv("AUTH_ALLOWED_EMAILS", raising=False)
    assert Settings(_env_file=None).auth_allowed_emails == []


def test_une_cle_de_signature_trop_courte_est_refusee(monkeypatch):
    """FR-037 : le démarrage échoue plutôt que de signer avec 8 caractères."""
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "trop-court")
    with pytest.raises(ValidationError):
        Settings()


def test_une_cle_de_signature_de_32_caracteres_est_acceptee(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "x" * 32)
    assert Settings().auth_session_secret_key == "x" * 32


def test_une_cle_de_signature_vide_vaut_non_configure(monkeypatch):
    """Une installation sans authentification doit démarrer (FR-036).

    C'est la distinction structurante : **vide** signifie « pas d'authentification
    sur ce site », et le site public reste intact ; **court** signifie « clé
    faible », et c'est un défaut de configuration qu'on refuse.
    """
    monkeypatch.setenv("AUTH_SESSION_SECRET_KEY", "")
    assert Settings().auth_session_secret_key == ""
