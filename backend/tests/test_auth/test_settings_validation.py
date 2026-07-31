"""Config validation guardrails around auth settings."""
import pytest


def test_session_secret_key_rejects_short_values(monkeypatch):
    """A short SESSION_SECRET_KEY (e.g. `dev`, `changeme`) must fail-fast."""
    from app.core import config

    config.get_settings.cache_clear()
    from pydantic import ValidationError

    monkeypatch.setenv("SESSION_SECRET_KEY", "too-short")
    with pytest.raises(ValidationError):
        config.Settings()
    config.get_settings.cache_clear()


def test_session_secret_key_accepts_empty_string(monkeypatch):
    """Empty string is the explicit "auth disabled" sentinel (FR-020)."""
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET_KEY", "")
    settings = config.Settings()
    assert settings.session_secret_key == ""
    config.get_settings.cache_clear()


def test_session_secret_key_accepts_long_values(monkeypatch):
    """A 32+ char key is accepted."""
    from app.core import config

    config.get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET_KEY", "x" * 32)
    settings = config.Settings()
    assert settings.session_secret_key == "x" * 32
    config.get_settings.cache_clear()
