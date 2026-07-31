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
