"""Tests de la configuration centralisée (`app.core.config`)."""

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
