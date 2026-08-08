"""Endpoint `/version` + résolution — issue #134.

Le repli fichier `VERSION` a été retiré : rien dans ce dépôt ne l'écrivait, et
c'est cette croyance qui a fait répondre « dev » en production pendant #134.
Reste `APP_VERSION` (poussée par le pipeline sur Render) ou `"dev"`.
"""
from app import version as version_module


def test_version_endpoint_expose_app_version_env(client, monkeypatch):
    monkeypatch.setenv("APP_VERSION", "v1.2.3")
    resp = client.get("/api/v1/version")
    assert resp.status_code == 200
    assert resp.json() == {"version": "v1.2.3"}


def test_version_fallback_dev_sans_env(monkeypatch):
    """Chemin local sans configuration : pas d'env → `"dev"`."""
    monkeypatch.delenv("APP_VERSION", raising=False)
    assert version_module.app_version() == "dev"


def test_version_fallback_dev_si_env_vide(monkeypatch):
    """`APP_VERSION` présente mais blanche → `"dev"`, jamais la chaîne vide :
    `""` ne veut pas dire « pas de version connue » pour le front.
    """
    monkeypatch.setenv("APP_VERSION", "   ")
    assert version_module.app_version() == "dev"


def test_version_endpoint_sans_config_retourne_dev(client, monkeypatch):
    """Contract-test end-to-end : sans env, `/version` répond `dev`."""
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
