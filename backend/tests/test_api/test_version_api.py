"""Endpoint `/version` + résolution en cascade — issue #134.

`app.version.app_version` a un `@lru_cache` (une seule lecture par processus).
Chaque test le vide via `.cache_clear()` avant lecture, sinon les cas
`APP_VERSION`, fichier `VERSION` et fallback se contaminent.
"""
from pathlib import Path

import pytest

from app import version as version_module


@pytest.fixture(autouse=True)
def _clear_cache():
    """Vide le cache LRU **avant et après** — sinon le premier test qui
    lit `app_version()` fige la valeur pour toute la suite.
    """
    version_module.app_version.cache_clear()
    yield
    version_module.app_version.cache_clear()


def test_version_endpoint_expose_app_version_env(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v1.2.3")
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    assert resp.json() == {"version": "v1.2.3"}


def test_version_env_ecrase_fichier(monkeypatch, tmp_path):
    """La variable `APP_VERSION` prime sur le fichier `VERSION`.

    L'env vient de la plateforme de déploiement, elle représente l'état
    présent du service ; le fichier est un repli figé au build. En cas de
    surcharge par ops, la vérité opérationnelle doit gagner.
    """
    fake_file = tmp_path / "VERSION"
    fake_file.write_text("v0.0.1")
    monkeypatch.setattr(version_module, "_VERSION_FILE", fake_file)
    monkeypatch.setenv("APP_VERSION", "v9.9.9")

    assert version_module.app_version() == "v9.9.9"


def test_version_lit_le_fichier_si_env_vide(monkeypatch, tmp_path):
    """Sans `APP_VERSION`, on lit le fichier `VERSION` — c'est le chemin
    nominal du buildCommand Render (`git describe --tags > VERSION`).
    """
    fake_file = tmp_path / "VERSION"
    fake_file.write_text("v0.1.3\n")  # trailing \n courant d'un `> fichier`
    monkeypatch.setattr(version_module, "_VERSION_FILE", fake_file)
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert version_module.app_version() == "v0.1.3"


def test_version_fallback_dev_si_ni_env_ni_fichier(monkeypatch, tmp_path):
    """Chemin local sans configuration : ni env, ni fichier → `"dev"`."""
    absent = tmp_path / "no-such-file"
    monkeypatch.setattr(version_module, "_VERSION_FILE", absent)
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert version_module.app_version() == "dev"


def test_version_fallback_dev_si_fichier_vide(monkeypatch, tmp_path):
    """Fichier `VERSION` présent mais vide (build sans tag récupérable) →
    on ne renvoie pas la chaîne vide, on retombe sur `"dev"` pour ne pas
    tromper le front (`""` ≠ « pas de version connue »).
    """
    empty = tmp_path / "VERSION"
    empty.write_text("   \n")
    monkeypatch.setattr(version_module, "_VERSION_FILE", empty)
    monkeypatch.delenv("APP_VERSION", raising=False)

    assert version_module.app_version() == "dev"


def test_version_endpoint_sans_config_retourne_dev(client, monkeypatch, tmp_path):
    """Contract-test end-to-end : sans env ni fichier, `/version` répond `dev`."""
    absent = tmp_path / "no-such-file"
    monkeypatch.setattr(version_module, "_VERSION_FILE", absent)
    monkeypatch.delenv("APP_VERSION", raising=False)

    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    assert resp.json() == {"version": "dev"}


def test_version_endpoint_ne_requiert_pas_dauth(client, monkeypatch):
    """`/version` doit rester public : un utilisateur non authentifié doit
    pouvoir remonter sa version pour un bug report.
    """
    monkeypatch.setenv("APP_VERSION", "v0.1.3")
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    # Aucun 401/403 sur cet endpoint, jamais.
    assert "version" in resp.json()


def test_version_file_pointe_vers_racine_backend():
    """Garde : le fichier `VERSION` est à la racine `backend/`, à côté de
    `pyproject.toml`. C'est là que le `buildCommand` Render écrit.
    """
    root = Path(version_module.__file__).resolve().parent.parent
    assert (root / "pyproject.toml").exists()
    assert version_module._VERSION_FILE == root / "VERSION"
